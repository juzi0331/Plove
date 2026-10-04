"""后台 — 站点（内容源）基础管理与高级设置。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    commit_now,
    get_db,
    get_registry,
    get_site_settings,
)
from app.api.v1.admin._audit import audit
from app.api.v1.admin._helpers import after_site_write, require_known_site
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin import (
    AdminSiteActionResult,
    AdminSiteListPayload,
    AdminSiteOrderRequest,
)
from app.schemas.admin_site_control import (
    SiteAdvancedSettingPayload,
    SiteAdvancedSettingUpdateRequest,
)
from app.schemas.envelope import Envelope, ok
from app.services import site_service, site_settings
from app.services.proxy_node_service import proxy_node_service
from app.services.site_settings import SiteSettingsStore

router = APIRouter(tags=["后台-站点管理"])


@router.get("/sites", response_model=Envelope[AdminSiteListPayload], summary="源列表（含开关、顺序与健康）")
def list_sites(
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[AdminSiteListPayload]:
    """包含被停用的源 —— 运维要能看到自己关掉了什么，而不是关掉之后就消失了。"""
    return ok(site_service.list_admin_sites(registry, store), request_id)


@router.post("/sites/{key}/disable", response_model=Envelope[AdminSiteActionResult], summary="停用源")
def disable_site(
    key: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[AdminSiteActionResult]:
    """把某个源从用户端藏起来，并且不再调用它（连 fork 都不会）。"""
    require_known_site(registry, key)
    site_settings.set_enabled(db, key, enabled=False)
    return after_site_write(
        db,
        registry,
        store,
        key,
        "disable_site",
        request_id,
        f"已停用 {key}：用户端不再显示它，内容接口会回 SITE_DISABLED",
    )


@router.post("/sites/{key}/enable", response_model=Envelope[AdminSiteActionResult], summary="启用源")
def enable_site(
    key: str,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[AdminSiteActionResult]:
    """恢复显示。守护状态刻意不动。"""
    require_known_site(registry, key)
    site_settings.set_enabled(db, key, enabled=True)
    return after_site_write(
        db,
        registry,
        store,
        key,
        "enable_site",
        request_id,
        f"已启用 {key}",
    )


@router.post("/sites/order", response_model=Envelope[AdminSiteListPayload], summary="调整源的顺序")
def order_sites(
    payload: AdminSiteOrderRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[AdminSiteListPayload]:
    """按给定顺序重排用户端列表（小的在前）。未知的 key 直接拒。"""
    site_settings.set_order(db, payload.keys, known=set(registry.keys()))
    commit_now(db)
    store.refresh(db, force=True)
    audit("order_sites", request_id, order=",".join(payload.keys))
    return ok(site_service.list_admin_sites(registry, store), request_id)


@router.get("/sites/{key}/advanced", response_model=Envelope[SiteAdvancedSettingPayload], summary="获取单站高级设置")
def get_site_advanced(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteAdvancedSettingPayload]:
    """包含前台自定义别名、角标、自定义超时、备注与独立代理配置。"""
    require_known_site(registry, key)
    config = store.config(key)
    return ok(
        SiteAdvancedSettingPayload(
            key=key,
            custom_name=config.custom_name,
            badge=config.badge,
            timeout_seconds=config.timeout_seconds,
            note=config.note,
            proxy_enabled=getattr(config, "proxy_enabled", False),
            proxy_url=getattr(config, "proxy_url", "") or "",
            proxy_node_id=getattr(config, "proxy_node_id", "") or "",
        ),
        request_id,
    )


@router.put("/sites/{key}/advanced", response_model=Envelope[SiteAdvancedSettingPayload], summary="更新单站高级设置")
def update_site_advanced(
    key: str,
    payload: SiteAdvancedSettingUpdateRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteAdvancedSettingPayload]:
    """更新别名、角标、超时秒数、备注及独立代理开关/地址/绑定的节点。"""
    require_known_site(registry, key)
    effective_proxy_url = payload.proxy_url
    if payload.proxy_enabled is False:
        payload.proxy_node_id = ""
        effective_proxy_url = ""
        try:
            proxy_node_service.bind_site(key, "direct")
        except Exception:
            pass
    elif payload.proxy_node_id is not None:
        if not payload.proxy_node_id or payload.proxy_node_id in ("direct", "none"):
            payload.proxy_enabled = False
            payload.proxy_node_id = ""
            effective_proxy_url = ""
            try:
                proxy_node_service.bind_site(key, "direct")
            except Exception:
                pass
        else:
            node = proxy_node_service.get_node(payload.proxy_node_id)
            if node:
                effective_proxy_url = node.get("proxy_url") or node.get("local_http_proxy")
                if payload.proxy_enabled is None:
                    payload.proxy_enabled = True
            try:
                proxy_node_service.bind_site(key, payload.proxy_node_id)
            except Exception:
                pass

    conf = site_settings.update_advanced(
        db,
        key,
        custom_name=payload.custom_name,
        badge=payload.badge,
        timeout_seconds=payload.timeout_seconds,
        note=payload.note,
        proxy_enabled=payload.proxy_enabled,
        proxy_url=effective_proxy_url if payload.proxy_enabled else "",
        proxy_node_id=payload.proxy_node_id if payload.proxy_enabled else "",
    )
    commit_now(db)
    store.refresh(db, force=True)
    audit("update_site_advanced", request_id, key=key)
    return ok(
        SiteAdvancedSettingPayload(
            key=key,
            custom_name=conf.custom_name,
            badge=conf.badge,
            timeout_seconds=conf.timeout_seconds,
            note=conf.note,
            proxy_enabled=getattr(conf, "proxy_enabled", False),
            proxy_url=getattr(conf, "proxy_url", "") or "",
            proxy_node_id=getattr(conf, "proxy_node_id", "") or "",
        ),
        request_id,
    )
