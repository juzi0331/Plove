"""网络代理、节点池管理与图片防盗链解密代理 API。"""

import importlib
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Header, Query, Response
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel, Field

from ..core.image_decoder import decode_image_via_sites, get_site_decoder
from ..engine.proxy_manager import proxy_manager

router = APIRouter(prefix="/api/v1/proxy", tags=["proxy"])

_get_site_decoder = get_site_decoder
_decode_image_via_sites = decode_image_via_sites


class ProxyConfigRequest(BaseModel):
    enabled: bool
    proxy_url: str = "http://127.0.0.1:10809"


class ProxyTestRequest(BaseModel):
    target_url: Optional[str] = "https://www.google.com"
    proxy_url: Optional[str] = None
    node_id: Optional[str] = None


class AddNodeRequest(BaseModel):
    raw_url: str = Field(..., description="vless:// 节点连接串或 http:// 代理地址")
    name: Optional[str] = Field("", description="自定义节点备注名称")
    local_port: Optional[int] = Field(10809, description="本地 Xray 映射端口")


class BindCrawlerRequest(BaseModel):
    site_key: str = Field(..., description="采集器英文标识，例如 huangguoai_com")
    node_id: str = Field(..., description="绑定的节点 ID，或 'direct' 直连，或 'default' 默认")


@router.get("", summary="获取当前代理与节点配置")
async def get_proxy_settings():
    return {
        "ok": True,
        "data": proxy_manager.get_config(),
        "error": None,
    }


@router.post("", summary="更新全局代理设置")
async def update_proxy_settings(req: ProxyConfigRequest):
    cfg = proxy_manager.set_config(enabled=req.enabled, proxy_url=req.proxy_url)
    return {
        "ok": True,
        "data": cfg,
        "error": None,
    }


@router.get("/nodes", summary="获取所有代理节点列表")
async def list_proxy_nodes():
    return {
        "ok": True,
        "data": {
            "nodes": proxy_manager.get_nodes(),
            "bindings": proxy_manager.get_bindings(),
        },
        "error": None,
    }


@router.post("/nodes", summary="添加或导入代理节点 (支持 VLESS / HTTP)")
async def add_proxy_node(req: AddNodeRequest):
    try:
        node = proxy_manager.add_node(
            raw_input=req.raw_url,
            custom_name=req.name or "",
            local_port=req.local_port or 10809,
        )
        return {
            "ok": True,
            "data": node,
            "error": None,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "data": None, "error": {"message": str(exc)}},
        )


@router.delete("/nodes/{node_id}", summary="删除代理节点")
async def delete_proxy_node(node_id: str):
    success = proxy_manager.delete_node(node_id)
    return {
        "ok": success,
        "data": {"deleted": success},
        "error": None if success else {"message": "节点不存在"},
    }


@router.post("/bind", summary="为指定采集器绑定节点")
async def bind_crawler(req: BindCrawlerRequest):
    try:
        res = proxy_manager.set_crawler_binding(site_key=req.site_key, node_id=req.node_id)
        return {
            "ok": True,
            "data": res,
            "error": None,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "data": None, "error": {"message": str(exc)}},
        )


@router.get("/nodes/{node_id}/xray-config", summary="导出指定 VLESS 节点的 Xray 配置文件")
async def export_xray_config(
    node_id: str,
    http_port: int = Query(10809, description="本地 HTTP 代理端口"),
    socks_port: int = Query(10808, description="本地 SOCKS5 代理端口"),
):
    try:
        cfg = proxy_manager.export_xray_config(node_id, http_port=http_port, socks_port=socks_port)
        return {
            "ok": True,
            "data": {
                "config_json": cfg,
                "config_str": __import__("json").dumps(cfg, indent=2, ensure_ascii=False),
            },
            "error": None,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "data": None, "error": {"message": str(exc)}},
        )


@router.post("/test", summary="测试代理连通性")
async def test_proxy_connection(req: ProxyTestRequest):
    res = await proxy_manager.test_connection(
        target_url=req.target_url or "https://www.google.com",
        custom_proxy=req.proxy_url,
        node_id=req.node_id,
    )
    return {
        "ok": True,
        "data": res,
        "error": None,
    }


@router.get("/image", summary="图片防盗链代理与密文流式解密中继")
async def proxy_image(
    url: str = Query(..., description="目标图片完整公网 URL"),
    site: Optional[str] = Query(None, description="来源站点 Key，用于自动加载站点专用解密钩子"),
    referer: Optional[str] = Query(None, description="自定义 Referer 防盗链欺骗"),
):
    """代理加载第三方图片，自动欺骗 Referer，并调用适配器 decode_image 自动解密加密图片。"""
    clean_url = url.strip()
    if not clean_url:
        return Response(status_code=400, content=b"Missing url")

    parsed = urlparse(clean_url)
    default_referer = f"{parsed.scheme}://{parsed.netloc}/"
    use_referer = referer or default_referer

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": use_referer,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    # 获取该站点生效的代理
    proxy = proxy_manager.get_site_proxy(site)

    content = None
    c_type = None

    # 1. 若配置了代理，优先尝试通过代理抓取
    if proxy:
        try:
            async with httpx.AsyncClient(proxy=proxy, verify=False, timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(clean_url, headers=headers)
                if resp.status_code == 200:
                    content = resp.content
                    c_type = resp.headers.get("content-type", "image/jpeg")
        except Exception:
            pass

    # 2. 直连抓取（若未配置代理，或代理请求失败，自动退回直连兜底）
    if content is None:
        try:
            async with httpx.AsyncClient(proxy=None, verify=False, timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(clean_url, headers=headers)
                if resp.status_code != 200:
                    return Response(
                        content=f"Image fetch error: HTTP {resp.status_code}".encode("utf-8"),
                        status_code=resp.status_code,
                        media_type="text/plain",
                    )
                content = resp.content
                c_type = resp.headers.get("content-type", "image/jpeg")
        except Exception as exc:
            return Response(
                content=f"Fetch Image Failed: {exc}".encode("utf-8"),
                status_code=502,
                media_type="text/plain",
            )

    # 尝试解密可能存在的密文图片
    decoded = _decode_image_via_sites(content, site=site)
    if decoded is not None:
        content, c_type = decoded

    return Response(
        content=content,
        media_type=c_type or "image/jpeg",
        headers={
            "Cache-Control": "public, max-age=604800, immutable",
            "Access-Control-Allow-Origin": "*",
            "X-Proxy-By": "Plove-Crawler-Image-Proxy",
        },
    )
