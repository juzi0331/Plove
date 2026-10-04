"""体验模块 API 路由集合导出。"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.experience.api.admin_experience import router as admin_router
from app.modules.experience.api.public_bootstrap import router as bootstrap_router
from app.modules.experience.api.public_pages import router as pages_router

experience_v2_router = APIRouter()
experience_v2_router.include_router(bootstrap_router)
experience_v2_router.include_router(pages_router)
experience_v2_router.include_router(admin_router)

__all__ = ["experience_v2_router"]
