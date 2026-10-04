"""后台 — 跨源并发聚合搜索。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_registry
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin_extended import AggregateSearchPayload
from app.schemas.envelope import Envelope, ok
from app.services import playground_service

router = APIRouter(tags=["后台-聚合搜索"])


@router.get("/search/aggregate", response_model=Envelope[AggregateSearchPayload], summary="跨源并发聚合搜索")
def search_aggregate(
    kw: str = Query(..., min_length=1, description="搜索关键词"),
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
) -> Envelope[AggregateSearchPayload]:
    """并发调度所有已启用的爬虫，横向比对各站点返回结果条数、耗时与支持状态。"""
    res = playground_service.aggregate_search(registry, kw=kw)
    return ok(res, request_id)
