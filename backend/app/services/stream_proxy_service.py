"""HLS 视频流防盗链与媒体解封装代理服务（阶段 9 核心实现）。

针对第三方视频源站（如 rou.video 等）：
1. 伪装媒体格式（如伪装成 PNG 图片容器封装的 m3u8 清单或 MPEG-TS 分片）；
2. 严格来源白名单（防盗链 Referer / Origin 限制、403 禁止直连）；
3. 动态短效时效签名。

本服务提供：
1. /proxy/stream/m3u8：拉取上游清单，调用站点 decode_media 钩子解封装，递归改写其中的分片与密钥地址；
2. /proxy/stream/segment：拉取上游分片，调用站点 decode_media 钩子解封装（如还原 0x47 TS 流），输出标准 video/mp2t；
3. /proxy/stream/key：拉取上游解密密钥，输出标准 application/octet-stream。
"""

from __future__ import annotations

import importlib
import logging
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

from app.core.security import is_safe_public_url

logger = logging.getLogger("stream_proxy")

# 注入爬虫目录以便动态加载各站点适配器媒体解密/解封装钩子
_crawler_dir = Path(__file__).resolve().parents[3] / "crawler"
if _crawler_dir.is_dir() and str(_crawler_dir) not in sys.path:
    sys.path.insert(0, str(_crawler_dir))

# 内存缓存站点媒体解码器映射表 {site_key: decoder_callable}
_site_media_decoders: dict[str, Any] = {}

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def get_site_media_decoder(site_key: str) -> Any | None:
    """获取指定站点的媒体解码器 decode_media 钩子（如果有的话）。"""
    if site_key in _site_media_decoders:
        return _site_media_decoders[site_key]
    try:
        mod = importlib.import_module(f"sites.{site_key}")
        decoder = getattr(mod, "decode_media", None)
        if decoder is None:
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if isinstance(attr, type) and hasattr(attr, "decode_media"):
                    decoder = getattr(attr, "decode_media")
                    break
        _site_media_decoders[site_key] = decoder
        return decoder
    except Exception as exc:
        logger.debug("站点 %s 未提供 decode_media 钩子: %s", site_key, exc)
        _site_media_decoders[site_key] = None
        return None


def _decode_media_content(content: bytes, site: str | None = None) -> bytes:
    """尝试通过站点插件解密/解封装媒体内容。若无适配器或解密失败，返回原字节。"""
    if not content or len(content) < 16:
        return content

    if site:
        decoder = get_site_media_decoder(site)
        if callable(decoder):
            try:
                decoded = decoder(content)
                if decoded and isinstance(decoded, (bytes, bytearray)):
                    return bytes(decoded)
            except Exception as exc:
                logger.warning("调用站点 %s decode_media 解码失败: %s", site, exc)

    return content


def _get_proxy_url_for_site(site: str | None) -> str | None:
    """获取站点代理，若无站点专属代理则回退全局代理配置或环境变量。"""
    site_proxy = None
    if site:
        try:
            from app.crawler.runner import _get_proxy_for_site
            site_proxy = _get_proxy_for_site(_crawler_dir, site)
        except Exception as exc:
            logger.debug("获取站点代理异常 (%s): %s", site, exc)
    if not site_proxy:
        import os
        site_proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("http_proxy")
            or os.environ.get("ALL_PROXY")
            or os.environ.get("all_proxy")
        )
    return site_proxy or None


def _create_http_client(site: str | None, timeout: float) -> httpx.Client:
    proxy = _get_proxy_url_for_site(site)
    return httpx.Client(proxy=proxy, follow_redirects=True, timeout=timeout)


def _build_upstream_headers(url: str, custom_referer: str | None = None) -> dict[str, str]:
    """为上游源站请求构造合法伪造头。"""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    referer = custom_referer or f"{origin}/"
    return {
        "User-Agent": DEFAULT_UA,
        "Referer": referer,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def fetch_and_rewrite_m3u8(
    upstream_url: str,
    site: str | None = None,
    custom_referer: str | None = None,
    token: str | None = None,
) -> tuple[str, str]:
    """拉取上游 m3u8 清单，解封装并重写其中的分片与密钥地址。

    返回: (rewritten_m3u8_text, content_type)
    """
    proxy_url = _get_proxy_url_for_site(site)
    resolve_dns = False if proxy_url else True
    if not is_safe_public_url(upstream_url, resolve_dns=resolve_dns):
        raise ValueError(f"不合规或受保护的流媒体地址: {upstream_url}")

    headers = _build_upstream_headers(upstream_url, custom_referer)
    with _create_http_client(site=site, timeout=20.0) as client:
        resp = client.get(upstream_url, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"上游清单返回 HTTP {resp.status_code}: {upstream_url}")

        final_url = str(resp.url)
        if final_url != upstream_url and not is_safe_public_url(final_url, resolve_dns=resolve_dns):
            raise ValueError(f"清单重定向到不安全地址: {final_url}")
        raw_body = resp.content

    # 1. 尝试解封装（如 rou.video 伪装成 PNG 的 zlib 压缩清单）
    payload = _decode_media_content(raw_body, site=site)
    if not payload.startswith(b"#EXTM3U") and raw_body.startswith(b"#EXTM3U"):
        payload = raw_body

    text = payload.decode("utf-8", "replace")
    if not text.startswith("#EXTM3U"):
        # 即使上游缺失 #EXTM3U 标签，若包含分片也做容错
        if "#EXTINF" not in text and "#EXT-X-STREAM-INF" not in text:
            raise RuntimeError(f"解析后的内容不是有效 HLS 清单（长度 {len(text)} 字节）")

    # 2. 改写清单中的 URI
    rewritten = rewrite_m3u8_content(text, base_url=final_url, site=site, token=token)
    return rewritten, "application/vnd.apple.mpegurl; charset=utf-8"


def rewrite_m3u8_content(
    m3u8_text: str,
    base_url: str,
    site: str | None = None,
    token: str | None = None,
) -> str:
    """改写 m3u8 清单文本，将所有变体、分片与密钥链接路由到后端流中继。"""
    site_param = f"&site={quote(site)}" if site else ""
    token_param = f"&token={quote(token)}" if token else ""
    lines = m3u8_text.splitlines()
    output_lines: list[str] = []
    is_variant_stream = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            output_lines.append(line)
            continue

        # 处理 #EXT-X-STREAM-INF (变体主清单)
        if stripped.startswith("#EXT-X-STREAM-INF:"):
            is_variant_stream = True
            output_lines.append(line)
            continue

        # 处理 #EXT-X-KEY (AES-128 加密密钥)
        if stripped.startswith("#EXT-X-KEY:"):
            # 匹配 URI="..."
            def replace_key_uri(match: re.Match) -> str:
                original_uri = match.group(1)
                abs_key_url = urljoin(base_url, original_uri)
                proxy_key_url = f"/api/v1/proxy/stream/key?url={quote(abs_key_url)}{site_param}{token_param}"
                return f'URI="{proxy_key_url}"'

            new_line = re.sub(r'URI="([^"]+)"', replace_key_uri, line)
            output_lines.append(new_line)
            continue

        # 处理 #EXT-X-MAP (fMP4 初始化分片)
        if stripped.startswith("#EXT-X-MAP:"):
            def replace_map_uri(match: re.Match) -> str:
                original_uri = match.group(1)
                abs_map_url = urljoin(base_url, original_uri)
                proxy_seg_url = f"/api/v1/proxy/stream/segment?url={quote(abs_map_url)}{site_param}{token_param}"
                return f'URI="{proxy_seg_url}"'

            new_line = re.sub(r'URI="([^"]+)"', replace_map_uri, line)
            output_lines.append(new_line)
            continue

        # 其他标签保持不变
        if stripped.startswith("#"):
            output_lines.append(line)
            continue

        # 非注释行：变体流地址或媒体分片地址
        abs_target_url = urljoin(base_url, stripped)
        if is_variant_stream:
            # 变体流子清单 -> 继续走 m3u8 中继
            proxy_url = f"/api/v1/proxy/stream/m3u8?url={quote(abs_target_url)}{site_param}{token_param}"
            is_variant_stream = False
        else:
            # 媒体切片 -> 走 segment 中继
            proxy_url = f"/api/v1/proxy/stream/segment?url={quote(abs_target_url)}{site_param}{token_param}"

        output_lines.append(proxy_url)

    return "\n".join(output_lines)


def fetch_and_decode_segment(
    upstream_url: str,
    site: str | None = None,
    custom_referer: str | None = None,
    range_header: str | None = None,
) -> tuple[bytes, str, int, dict[str, str]]:
    """拉取上游媒体切片，解封装并返回真实二进制数据（如 MPEG-TS）。

    返回: (data_bytes, media_type, status_code, extra_headers)
    """
    proxy_url = _get_proxy_url_for_site(site)
    resolve_dns = False if proxy_url else True
    if not is_safe_public_url(upstream_url, resolve_dns=resolve_dns):
        raise ValueError(f"不合规或受保护的流媒体切片地址: {upstream_url}")

    headers = _build_upstream_headers(upstream_url, custom_referer)
    # ⚠️ 关键：若站点具有媒体解密/解封装钩子（如伪装成 PNG 的 MPEG-TS），切不可将 Range 传给上游源站！
    # 因为对压缩或封装文件进行部分 Range 抓取会导致解密/解压缩损坏。
    # 此时应全量拉取上游密文/伪装体，解密完成后再由本地对解密后的媒体流实施 Range 切片切块。
    has_decoder = callable(get_site_media_decoder(site)) if site else False
    if range_header and not has_decoder:
        headers["Range"] = range_header

    with _create_http_client(site=site, timeout=30.0) as client:
        resp = client.get(upstream_url, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"上游分片返回 HTTP {resp.status_code}: {upstream_url}")

        final_url = str(resp.url)
        if final_url != upstream_url and not is_safe_public_url(final_url, resolve_dns=resolve_dns):
            raise ValueError(f"切片重定向到不安全地址: {final_url}")

        raw_body = resp.content
        upstream_content_type = resp.headers.get("content-type") or ""

    # 调用解封装钩子（将伪装 PNG 剥除，还原出 TS/MP4 数据）
    decoded = _decode_media_content(raw_body, site=site)

    # 嗅探真实媒体 MIME 类型
    media_type = "video/mp2t"
    if decoded.startswith(b"\x47"):
        media_type = "video/mp2t"
    elif len(decoded) >= 8 and decoded[4:8] in (b"ftyp", b"moof", b"mdat"):
        media_type = "video/mp4"
    elif "mpegurl" in upstream_content_type.lower():
        media_type = "application/vnd.apple.mpegurl"

    resp_headers: dict[str, str] = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Cache-Control": "public, max-age=86400, immutable",
    }

    # 处理客户端 Range 请求
    if range_header and range_header.startswith("bytes="):
        try:
            byte_range = range_header.split("=", 1)[1].strip()
            parts = byte_range.split("-")
            total_len = len(decoded)
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else total_len - 1
            start = max(0, start)
            end = min(total_len - 1, end)
            if start <= end:
                sliced = decoded[start : end + 1]
                resp_headers["Content-Range"] = f"bytes {start}-{end}/{total_len}"
                resp_headers["Accept-Ranges"] = "bytes"
                return sliced, media_type, 206, resp_headers
        except Exception:
            pass

    resp_headers["Accept-Ranges"] = "bytes"
    return decoded, media_type, 200, resp_headers


def fetch_and_decode_key(
    upstream_url: str,
    site: str | None = None,
    custom_referer: str | None = None,
) -> tuple[bytes, str]:
    """拉取 AES-128 加密密钥，解封装后返回。"""
    proxy_url = _get_proxy_url_for_site(site)
    resolve_dns = False if proxy_url else True
    if not is_safe_public_url(upstream_url, resolve_dns=resolve_dns):
        raise ValueError(f"不合规或受保护的密钥地址: {upstream_url}")

    headers = _build_upstream_headers(upstream_url, custom_referer)
    with _create_http_client(site=site, timeout=15.0) as client:
        resp = client.get(upstream_url, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"上游密钥返回 HTTP {resp.status_code}: {upstream_url}")
        final_url = str(resp.url)
        if final_url != upstream_url and not is_safe_public_url(final_url, resolve_dns=resolve_dns):
            raise ValueError(f"密钥重定向到不安全地址: {final_url}")
        raw = resp.content
        if len(raw) > 8192:
            raise ValueError("密钥响应体异常过大")

    decoded = _decode_media_content(raw, site=site)
    return decoded, "application/octet-stream"
