"""站点相关的业务编排。薄，但它是 api 与 crawler 之间的那道墙。

### 两件事在这里定死

1. **顺序**：用户端看到的站点列表按后台设定的 ``sort_order`` 排（同序时按 key），
   这样"把快的那台放前面"是一个运维动作，而不是又一次改代码；
2. **停用**：停用的源既不在列表里，也不能通过 ``GET /sites/{key}`` 被单独问到 ——
   只藏列表是不够的，客户端手里可能存着旧 key。
"""

from __future__ import annotations

from app.core.errors import AppError, ErrorCode
from app.crawler.registry import SiteRegistry
from app.schemas.admin import AdminSiteItem, AdminSiteListPayload, SiteHealth
from app.schemas.site import SiteListPayload, SiteMeta
from app.services.site_settings import SiteSettingsStore


def _decorate_meta(meta: SiteMeta, store: SiteSettingsStore) -> SiteMeta:
    config = store.config(meta.key)
    name = config.custom_name if config.custom_name else meta.name
    return meta.model_copy(
        update={
            "name": name,
            "custom_name": config.custom_name,
            "badge": config.badge,
        }
    )


def list_sites(registry: SiteRegistry, store: SiteSettingsStore) -> SiteListPayload:
    """能拿到 meta 的源才会出现在列表里（挂掉的源会被跳过并记日志），
    且**不含被停用的源** —— 过滤发生在 ``registry.all_meta()`` 里（它走 enabled_keys）。"""
    metas = [_decorate_meta(m, store) for m in registry.all_meta()]
    metas.sort(key=lambda meta: store.order_key(meta.key))
    return SiteListPayload(sites=metas)


def list_admin_sites(registry: SiteRegistry, store: SiteSettingsStore) -> AdminSiteListPayload:
    """后台的源列表：**包含被停用的源**，外加开关、顺序与健康。"""
    health = {item["site"]: item for item in registry.guards()}
    keys = store.sort_keys(registry.keys())
    return AdminSiteListPayload(sites=[site_item(registry, store, key, health.get(key)) for key in keys])


def site_item(
    registry: SiteRegistry,
    store: SiteSettingsStore,
    key: str,
    health: dict | None = None,
) -> AdminSiteItem:
    """把某个源拼成后台列表里的一行。开关/顺序来自配置，名称/能力来自 meta。"""
    config = store.config(key)
    name, version, mode, capabilities, meta_error = key, "", "direct", [], None
    try:
        meta = registry.meta(key)
        name, version, mode = meta.name, meta.version, meta.mode
        capabilities = list(meta.capabilities)
    except AppError as exc:
        meta_error = f"{exc.code.value}: {exc.message}"

    if config.custom_name:
        name = f"{config.custom_name} ({name})" if name != key else config.custom_name

    snapshot = health if health is not None else registry.guard(key).snapshot()
    return AdminSiteItem(
        key=key,
        name=name,
        enabled=config.enabled,
        sort_order=config.sort_order,
        note=config.note,
        version=version,
        mode=mode,
        capabilities=capabilities,
        meta_error=meta_error,
        health=SiteHealth(**snapshot),
        proxy_enabled=getattr(config, "proxy_enabled", False),
        proxy_url=getattr(config, "proxy_url", "") or "",
        proxy_node_id=getattr(config, "proxy_node_id", "") or "",
    )


def get_site(registry: SiteRegistry, store: SiteSettingsStore, key: str) -> SiteMeta:
    if not store.is_enabled(key):
        raise AppError(ErrorCode.SITE_DISABLED, f"源 {key} 已在后台停用")
    return _decorate_meta(registry.meta(key), store)
