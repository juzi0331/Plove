from fastapi import APIRouter

from .routes_explore import router as explore_router
from .routes_generator import router as generator_router
from .routes_proxy import router as proxy_router
from .routes_rules import router as rules_router
from .routes_tester import router as tester_router
from .visual_proxy_assets import build_injected_visual_proxy_html

_build_injected_visual_proxy_html = build_injected_visual_proxy_html

router = APIRouter(prefix="/api/v1/smart", tags=["智能采集与脚本工坊"])

router.include_router(explore_router)
router.include_router(generator_router)
router.include_router(tester_router)
router.include_router(rules_router)
router.include_router(proxy_router)

__all__ = ["router", "_build_injected_visual_proxy_html", "build_injected_visual_proxy_html"]
