"""站点接口：有哪些源、每个源会什么。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_registry, get_site_settings, require_device
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.envelope import Envelope, ok
from app.schemas.site import SiteListPayload, SiteMeta
from app.services import site_service
from app.services.site_settings import SiteSettingsStore

#: 守卫挂在 router 上，而不是塞进每个路由 —— 加接口时才不会忘记加鉴权
router = APIRouter(tags=["站点"], dependencies=[Depends(require_device)])


@router.get("/sites", response_model=Envelope[SiteListPayload], summary="站点列表")
def list_sites(
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    settings: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteListPayload]:
    """用户端看到的站点列表：**不含被后台停用的源**，且按后台设定的顺序。"""
    return ok(site_service.list_sites(registry, settings), request_id)


@router.get("/sites/{key}", response_model=Envelope[SiteMeta], summary="单个站点信息")
def get_site(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    settings: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteMeta]:
    """停用的源会回 ``SITE_DISABLED`` —— 光把它从列表里藏起来是不够的。"""
    return ok(site_service.get_site(registry, settings, key), request_id)
