"""系统状态与公共工具接口（免认证，前台/后台通用）。

1. /system/status: 全站维护模式状态、前台公告广播
2. /proxy/image: 图片防盗链代理（支持 ETag 协商缓存与源站防盗链欺骗）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import Response as RawResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.middleware import get_request_id
from app.schemas.admin_extended import SystemStatusPayload
from app.schemas.envelope import Envelope, ok
from app.services import image_proxy_service, system_service

router = APIRouter(tags=["系统与公共工具"])


@router.get("/system/status", response_model=Envelope[SystemStatusPayload], summary="全站运行状态与公告")
def system_status(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemStatusPayload]:
    status = system_service.get_public_system_status(db)
    return ok(status, request_id)


@router.get("/proxy/image", summary="图片防盗链代理")
def proxy_image(
    url: str = Query(..., description="目标图片完整公网 URL"),
    referer: str | None = Query(None, description="可选的自定义 Referer"),
    site: str | None = Query(None, description="可选的来源站点 Key，用于调用站点专用解码插件"),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
) -> RawResponse:
    """代理获取带有防盗链（403）或跨域限制的第三方图片。

    - 自动欺骗 Referer 与 User-Agent
    - 委托站点适配器钩子自动解密（如黄果短剧等加密图床）
    - 本地磁盘/内存持久化缓存
    - 支持 ETag 304 快速协商
    """
    try:
        content, content_type, etag = image_proxy_service.fetch_image_with_cache(
            url=url,
            custom_referer=referer,
            site=site,
        )
    except Exception as exc:
        return RawResponse(
            content=f"Image Proxy Error: {exc}".encode("utf-8"),
            status_code=502,
            media_type="text/plain",
        )

    # 304 协商缓存
    if if_none_match and if_none_match.strip() == etag:
        return RawResponse(status_code=304, headers={"ETag": etag})

    return RawResponse(
        content=content,
        status_code=200,
        media_type=content_type,
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=604800, immutable",
            "X-Proxy-By": "Plove-Image-Proxy",
        },
    )
