"""后台管理路由聚合。所有子域路由在这里统一组装。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.api.v1.admin import (
    cache,
    codes,
    crawlers,
    devices,
    playground,
    proxy,
    proxy_engine,
    proxy_nodes,
    search,
    site_control,
    sites,
    status,
    system,
)

# 公共 admin_router：统一管理 /admin 前缀与 require_admin 鉴权守卫
admin_router = APIRouter(
    prefix="/admin",
    tags=["后台"],
    dependencies=[Depends(require_admin)],
)

# 挂载各业务子域路由
admin_router.include_router(status.router)
admin_router.include_router(codes.router)
admin_router.include_router(devices.router)
admin_router.include_router(sites.router)
admin_router.include_router(site_control.router)
admin_router.include_router(crawlers.router)
admin_router.include_router(cache.router)
admin_router.include_router(playground.router)
admin_router.include_router(search.router)
admin_router.include_router(proxy.router)
admin_router.include_router(system.router)
admin_router.include_router(proxy_nodes.router)
admin_router.include_router(proxy_engine.router)

# 保持对旧引用兼容
router = admin_router

__all__ = ["admin_router", "router"]
