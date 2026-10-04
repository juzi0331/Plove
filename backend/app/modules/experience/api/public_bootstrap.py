"""面向客户端的公开体验与配置协商路由 (/api/v2/client)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.middleware import get_request_id
from app.modules.experience.application.resolve_bootstrap import (
    resolve_client_bootstrap,
    resolve_current_release_info,
)
from app.modules.experience.schemas.bootstrap import (
    ClientBootstrapPayload,
    ReleaseCurrentPayload,
)
from app.schemas.envelope import Envelope, ok

router = APIRouter(prefix="/client", tags=["客户端体验协商"])


@router.post(
    "/bootstrap",
    response_model=Envelope[ClientBootstrapPayload],
    summary="客户端启动配置协商",
)
def client_bootstrap(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ClientBootstrapPayload]:
    """匿名或已激活客户端均可获取当前发布的品牌、主题 Token、导航与播放参数。"""
    payload = resolve_client_bootstrap(db)
    return ok(payload, request_id)


@router.get(
    "/releases/current",
    response_model=Envelope[ReleaseCurrentPayload],
    summary="轻量查询当前发布版本与修订号",
)
def get_current_release_info(
    response: Response,
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[ReleaseCurrentPayload] | Response:
    """活跃客户端每 30 秒条件轮询版本。如果版本未变则返回 HTTP 304，节省网络带宽。"""
    info = resolve_current_release_info(db)
    etag = f'"{info.release_id}_r{info.revision}"'

    if if_none_match and if_none_match.strip() == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=15"})

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=15"
    return ok(info, request_id)
