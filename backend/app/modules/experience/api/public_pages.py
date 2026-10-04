"""面向客户端的公开页面 ViewModel 路由 (/api/v2/client/pages)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_content_cache, get_db, get_registry
from app.cache.content import ContentCache
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.modules.experience.application.build_page import build_page_view_model
from app.modules.experience.schemas.page import PageViewModel
from app.schemas.envelope import Envelope, ok

router = APIRouter(prefix="/client", tags=["客户端体验协商"])


@router.get(
    "/pages/{page_id}",
    response_model=Envelope[PageViewModel],
    summary="获取指定页面的服务端渲染视图模型",
)
def get_page_view_model(
    page_id: str,
    release_id: str | None = Query(None, description="可选的锁定发布快照 ID"),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    cache: ContentCache = Depends(get_content_cache),
) -> Envelope[PageViewModel]:
    """返回服务端根据已批准区块配置与实时 Catalog 数据组装后的 PageViewModel。"""
    vm = build_page_view_model(
        session=db,
        page_id=page_id,
        release_id=release_id,
        registry=registry,
        cache=cache,
    )
    return ok(vm, request_id)
