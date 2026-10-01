"""本地网络代理设置与连通性测试 API。"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from ..engine.proxy_manager import proxy_manager

router = APIRouter(prefix="/api/v1/proxy", tags=["proxy"])


class ProxyConfigRequest(BaseModel):
    enabled: bool
    proxy_url: str = "http://127.0.0.1:10809"


class ProxyTestRequest(BaseModel):
    target_url: Optional[str] = "https://www.google.com"


@router.get("", summary="获取当前代理配置")
async def get_proxy_settings():
    return {
        "ok": True,
        "data": proxy_manager.get_config(),
        "error": None,
    }


@router.post("", summary="更新代理配置并热加载生效")
async def update_proxy_settings(req: ProxyConfigRequest):
    cfg = proxy_manager.set_config(enabled=req.enabled, proxy_url=req.proxy_url)
    return {
        "ok": True,
        "data": cfg,
        "error": None,
    }


@router.post("/test", summary="测试代理连通性")
async def test_proxy_connection(req: ProxyTestRequest):
    res = await proxy_manager.test_connection(target_url=req.target_url or "https://www.google.com")
    return {
        "ok": True,
        "data": res,
        "error": None,
    }
