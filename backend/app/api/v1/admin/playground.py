"""后台 — 在线探针与试播台。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_content_cache,
    get_registry,
)
from app.api.v1.admin._audit import audit
from app.api.v1.admin._helpers import require_known_site
from app.cache.content import ContentCache
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin_extended import (
    PlaygroundProbeRequest,
    PlaygroundProbeResult,
)
from app.schemas.envelope import Envelope, ok
from app.services import playground_service

router = APIRouter(tags=["后台-探针"])


@router.post("/playground/probe", response_model=Envelope[PlaygroundProbeResult], summary="在线探针探测与试播解析")
def playground_probe(
    payload: PlaygroundProbeRequest,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[PlaygroundProbeResult]:
    """选站测试 home/category/detail/play，输出精准耗时、缓存命中状态、原始与洗后对比及 m3u8。"""
    require_known_site(registry, payload.site)
    res = playground_service.run_probe(registry, cache, payload)
    audit("playground_probe", request_id, site=payload.site, command=payload.command, status=res.status)
    return ok(res, request_id)
