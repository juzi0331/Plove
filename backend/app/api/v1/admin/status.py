"""后台 — 系统总览与即时预热状态。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_content_cache,
    get_registry,
    get_warmup_runner,
)
from app.cache.content import ContentCache
from app.core.config import Settings, get_settings
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin import (
    AdminStatusPayload,
    CacheStats,
    RefreshResult,
    SiteHealth,
)
from app.schemas.envelope import Envelope, ok
from app.services.warmup_service import WarmupRunner

router = APIRouter(tags=["后台-总览"])


@router.get("/status", response_model=Envelope[AdminStatusPayload], summary="后台总览")
def status(
    request_id: str = Depends(get_request_id),
    settings: Settings = Depends(get_settings),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
    warmup: WarmupRunner = Depends(get_warmup_runner),
) -> Envelope[AdminStatusPayload]:
    """缓存 + 每个源的健康 + 上次预热的结果，一次拿全。"""
    payload = AdminStatusPayload(
        env=settings.env,
        sites=[SiteHealth(**item) for item in registry.guards()],
        cache=CacheStats(**cache.stats()),
        warmup=warmup.status(),
    )
    return ok(payload, request_id)


@router.post("/cache/refresh", response_model=Envelope[RefreshResult], summary="立即刷新缓存")
def refresh_cache(
    wait: bool = Query(
        False,
        description="true = 等这一轮跑完再返回（会慢，可能十几秒）；"
        "默认立刻返回，用 /admin/status 看结果",
    ),
    request_id: str = Depends(get_request_id),
    warmup: WarmupRunner = Depends(get_warmup_runner),
) -> Envelope[RefreshResult]:
    """手动跑一次预热：把每个源的首页与前几个分类重新抓一遍。"""
    if wait:
        result = warmup.run_once(reason="手动")
        return ok(
            RefreshResult(
                started=True,
                message="已同步完成一轮预热",
                warmup=result,
            ),
            request_id,
        )

    started = warmup.start_in_background(reason="手动")
    return ok(
        RefreshResult(
            started=started,
            message=(
                "已开始预热，用 GET /api/v1/admin/status 看进度"
                if started
                else "已经有一轮预热在进行中，没有重复启动"
            ),
        ),
        request_id,
    )
