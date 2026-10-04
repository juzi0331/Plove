"""系统状态与公共工具接口（免认证，前台/后台通用）。

1. /system/status: 全站维护模式状态、前台公告广播
2. /proxy/image: 图片防盗链代理（支持 ETag 协商缓存与源站防盗链欺骗）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response as RawResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin, require_proxy_access
from app.core.logging import get_logger
from app.core.middleware import get_request_id
from app.schemas.admin_extended import SystemStatusPayload
from app.schemas.envelope import Envelope, ok
from app.services import image_proxy_service, stream_proxy_service, system_service

logger = get_logger("system")
router = APIRouter(tags=["系统与公共工具"])


@router.get("/system/status", response_model=Envelope[SystemStatusPayload], summary="全站运行状态与公告")
def system_status(
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Envelope[SystemStatusPayload]:
    status = system_service.get_public_system_status(db)
    return ok(status, request_id)


@router.get(
    "/proxy/image",
    summary="图片防盗链代理",
    dependencies=[Depends(require_proxy_access)],
)
def proxy_image(
    url: str = Query(..., description="目标图片完整公网 URL"),
    referer: str | None = Query(None, description="可选的自定义 Referer"),
    site: str | None = Query(None, description="可选的来源站点 Key，用于调用站点专用解码插件"),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
) -> RawResponse:
    """代理获取带有防盗链（403）或跨域限制的第三方图片。

    - 必须具备活跃设备令牌或管理权限
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
        logger.error("Image Proxy Error: %s", exc)
        return RawResponse(
            content=b"Image Proxy Error",
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
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


@router.get(
    "/proxy/stream/m3u8",
    summary="HLS 清单中继与重写",
    dependencies=[Depends(require_proxy_access)],
)
def proxy_stream_m3u8(
    url: str = Query(..., description="目标 m3u8 清单完整公网 URL"),
    site: str | None = Query(None, description="可选来源站点 Key，用于调用站点专用媒体解码插件"),
    referer: str | None = Query(None, description="可选自定义 Referer"),
    token: str | None = Query(None, description="可选的设备或鉴权令牌"),
    x_device_token: str | None = Header(None, alias="X-Device-Token"),
) -> RawResponse:
    """拉取上游 HLS 清单，调用 decode_media 解封装并重写其中的分片与密钥地址。"""
    try:
        active_token = x_device_token or token
        rewritten_text, content_type = stream_proxy_service.fetch_and_rewrite_m3u8(
            upstream_url=url,
            site=site,
            custom_referer=referer,
            token=active_token,
        )
        return RawResponse(
            content=rewritten_text.encode("utf-8"),
            status_code=200,
            media_type=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-Proxy-By": "Plove-Stream-Proxy",
            },
        )
    except Exception as exc:
        logger.error("Stream Playlist Proxy Error: %s", exc)
        return RawResponse(
            content=b"Stream Playlist Proxy Error",
            status_code=502,
            media_type="text/plain",
            headers={"Access-Control-Allow-Origin": "*"},
        )


@router.get(
    "/proxy/stream/segment",
    summary="HLS 分片中继与解封装",
    dependencies=[Depends(require_proxy_access)],
)
def proxy_stream_segment(
    url: str = Query(..., description="目标分片完整公网 URL"),
    site: str | None = Query(None, description="可选来源站点 Key，用于调用站点专用媒体解码插件"),
    referer: str | None = Query(None, description="可选自定义 Referer"),
    range_header: str | None = Header(None, alias="Range"),
) -> RawResponse:
    """拉取上游分片，调用站点 decode_media 解封装（还原纯正 TS/MP4 流），支持 Range。"""
    try:
        data, media_type, status_code, extra_headers = stream_proxy_service.fetch_and_decode_segment(
            upstream_url=url,
            site=site,
            custom_referer=referer,
            range_header=range_header,
        )
        return RawResponse(
            content=data,
            status_code=status_code,
            media_type=media_type,
            headers=extra_headers,
        )
    except Exception as exc:
        logger.error("Stream Segment Proxy Error: %s", exc)
        return RawResponse(
            content=b"Stream Segment Proxy Error",
            status_code=502,
            media_type="text/plain",
            headers={"Access-Control-Allow-Origin": "*"},
        )


@router.get(
    "/proxy/stream/key",
    summary="HLS 加密密钥中继",
    dependencies=[Depends(require_proxy_access)],
)
def proxy_stream_key(
    url: str = Query(..., description="目标密钥完整公网 URL"),
    site: str | None = Query(None, description="可选来源站点 Key"),
    referer: str | None = Query(None, description="可选自定义 Referer"),
) -> RawResponse:
    """拉取 AES-128 加密密钥，解封装后返回二进制密钥。"""
    try:
        data, media_type = stream_proxy_service.fetch_and_decode_key(
            upstream_url=url,
            site=site,
            custom_referer=referer,
        )
        return RawResponse(
            content=data,
            status_code=200,
            media_type=media_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Cache-Control": "public, max-age=86400, immutable",
            },
        )
    except Exception as exc:
        logger.error("Stream Key Proxy Error: %s", exc)
        return RawResponse(
            content=b"Stream Key Proxy Error",
            status_code=502,
            media_type="text/plain",
            headers={"Access-Control-Allow-Origin": "*"},
        )


@router.post(
    "/system/cache/clear",
    summary="清除运行时缓存与重置站点注册表",
    dependencies=[Depends(require_admin)],
)
def clear_system_cache(
    request_id: str = Depends(get_request_id),
):
    from app.api import deps
    deps.reset_runtime()
    cache = deps.get_content_cache(deps.get_settings())
    cache.clear()
    return ok({"message": "运行时缓存已清空，站点适配器与注册表已重置"}, request_id)


