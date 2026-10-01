"""v1 路由聚合。新增模块只在这里挂一次。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import activation, admin, catalog, health, sites, system

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
#: 激活接口不能有守卫 —— 没激活的客户端也要能调它
api_router.include_router(activation.router)
api_router.include_router(sites.router)
api_router.include_router(catalog.router)
#: 后台接口用的是**另一套**凭证（运维令牌），不是激活码
api_router.include_router(admin.router)

__all__ = ["api_router"]
