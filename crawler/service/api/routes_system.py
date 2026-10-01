"""系统与健康检查路由。"""

from fastapi import APIRouter
from ..engine.rule_manager import rule_manager

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "crawler_service",
        "loaded_rules": len(rule_manager.list_rules()),
    }


@router.get("/api/v1/meta")
async def get_service_meta():
    rules = rule_manager.list_rules()
    return {
        "ok": True,
        "data": {
            "name": "Plove Universal Crawler Service",
            "version": "1.0.0",
            "sites": [
                {
                    "key": r.key,
                    "name": r.name,
                    "base_url": r.base_url,
                    "data_type": r.data_type,
                    "mode": r.mode,
                }
                for r in rules
            ],
        },
        "error": None,
    }
