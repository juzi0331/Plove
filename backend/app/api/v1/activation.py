"""激活与会话接口。

这三个接口是**唯一不需要守卫**的：一个还没激活的客户端当然调不了需要守卫的接口，
否则它永远激活不了。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Security
from sqlalchemy.orm import Session

from app.api.deps import commit_now, device_token_header, get_content_cache, get_db, get_registry
from app.cache.content import ContentCache
from app.core.middleware import get_request_id
from app.core.rate_limit import RateLimitGuard
from app.crawler.registry import SiteRegistry
from app.schemas.activation import (
    ActivationResult,
    RedeemRequest,
    SessionState,
)
from app.schemas.catalog import VodItem
from app.schemas.envelope import Envelope, ok
from app.services import activation_service, catalog_service

router = APIRouter(tags=["激活"], prefix="/activation")
redeem_limiter = RateLimitGuard(limit=5, window_seconds=60, scope="redeem")


@router.post(
    "/redeem",
    response_model=Envelope[ActivationResult],
    summary="激活 / 在此设备继续",
    dependencies=[Depends(redeem_limiter)],
)
def redeem(
    payload: RedeemRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ActivationResult]:
    """首次激活只给 ``code``；被踢后用已存的 ``device_token`` 调一次就能抢回来。

    **这个动作刻意不自动做。**    客户端发现自己被踢之后应当停下来等用户手动点，
    否则两台设备会互相无限踢。

    提交必须**在这里**做：客户端拿到 200 之后一定会立刻重新拉内容
    （界面上的"被踢"错误态要靠它自己恢复），而 ``get_db`` 的自动提交
    跑在响应送出之后 —— 不显式提交，页面重新加载就会又收到
    ``SESSION_KICKED``。详见 :func:`app.api.deps.commit_now`。
    """
    result = activation_service.redeem(
        db,
        code=payload.code,
        device_token=payload.device_token,
        device_name=payload.device_name,
    )
    commit_now(db)
    return ok(result, request_id)


@router.post("/heartbeat", response_model=Envelope[SessionState], summary="心跳")
def heartbeat(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    token: str | None = Security(device_token_header),
) -> Envelope[SessionState]:
    """客户端按 ``heartbeat_interval_seconds`` 的频率来调。

    返回的 ``is_active`` 就是单会话模型的抓手：为 false 说明活跃位已经被别的设备拿走，
    客户端应当立即停播并提示。

    **服务端不做"离线超时释放"** —— 活跃位只在有人主动抢的时候才变。
    这样切后台、锁屏、网络抖动都不会误踢，也没有阈值要调。
    """
    return ok(activation_service.heartbeat(db, token), request_id)


@router.get("/trending", response_model=Envelope[list[VodItem]], summary="落地页现正热播与背景海报")
def trending(
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[list[VodItem]]:
    """未激活落地页使用的公开片单与封面数据（现正热播与背景海报墙）。"""
    items: list[VodItem] = []
    for key in list(registry.keys()):
        try:
            data = catalog_service.home(registry, cache, key)
            items = data.recommend or (data.sections[0].videos if data.sections else [])
            if items:
                break
        except Exception:
            continue
    return ok(items, request_id)

