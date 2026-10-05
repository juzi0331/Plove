"""图片抓取、安全校验与缓存协同。"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.core.security import is_safe_public_url
from app.services.image_proxy.cache import _hash_url, ensure_cache_dir
from app.services.image_proxy.config import get_image_proxy_config
from app.services.image_proxy.transform import _decode_image_dynamic


def _is_safe_url(url: str) -> bool:
    """安全校验：仅允许公网 http / https，阻止探测内网主机与云元数据。"""
    return is_safe_public_url(url)


def fetch_image_with_cache(
    url: str,
    custom_referer: str | None = None,
    timeout_seconds: float = 10.0,
    site: str | None = None,
) -> tuple[bytes, str, str]:
    """带有本地持久化缓存、动态防盗链与多级解密调度的图片抓取核心函数。"""
    url = (url or "").strip().strip("'\"`")
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith(("http://", "https://")) and "://" not in url:
        url = "https://" + url

    if not _is_safe_url(url):
        raise ValueError("不合规或受保护的图片地址")

    cfg = get_image_proxy_config()
    cdir = ensure_cache_dir()
    h = _hash_url(url)
    data_file = cdir / f"{h}.bin"
    meta_file = cdir / f"{h}.meta"

    etag = f'"{h}"'

    # 1. 检查本地磁盘持久化缓存（必须显式开启磁盘缓存时才读取）
    if cfg.disk_cache_enabled and data_file.exists() and meta_file.exists():
        try:
            content = data_file.read_bytes()
            c_type = meta_file.read_text(encoding="utf-8").strip() or "image/jpeg"
            clean_type = (c_type or "").split(";")[0].strip().lower()
            # 若缓存文件是历史未解密密文，尝试即时动态解密并自愈
            if not clean_type.startswith("image/"):
                decoded_cache = _decode_image_dynamic(content, url=url, site=site)
                if decoded_cache is not None:
                    content, c_type, _ = decoded_cache
                    try:
                        data_file.write_bytes(content)
                        meta_file.write_text(c_type, encoding="utf-8")
                    except Exception:
                        pass
            return content, c_type, etag
        except Exception:
            pass

    # 2. 远端抓取（优先检查外部 CDN 加速前缀规则）
    target_fetch_url = url
    for rule in getattr(cfg, "cdn_prefix_rules", []):
        if not getattr(rule, "enabled", True) or not getattr(rule, "prefix", ""):
            continue
        r_site = (getattr(rule, "site_key", "") or "").strip().lower()
        r_domain = (getattr(rule, "match_domain", "") or "").strip().lower()
        if r_site and site and r_site != site.strip().lower():
            continue
        if r_domain and r_domain not in url.lower():
            continue
        # 命中前缀加速规则：转由公共边缘 CDN 反代抓取
        if not url.startswith(rule.prefix):
            target_fetch_url = f"{rule.prefix}{url}"
        break

    parsed = urlparse(target_fetch_url)
    default_referer = f"{parsed.scheme}://{parsed.netloc}/"
    referer = custom_referer or default_referer

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        resp = client.get(target_fetch_url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"源站返回 HTTP {resp.status_code}")
        
        final_url = str(resp.url)
        if final_url != url and not is_safe_public_url(final_url):
            raise ValueError(f"图片重定向到不安全地址: {final_url}")

        content = resp.content
        c_type = resp.headers.get("content-type", "image/jpeg")

    # 委托多级动态图片解密调度链（后台规则库 -> 站点插件 -> 内置兜底）
    decoded = _decode_image_dynamic(content, url=url, site=site)
    if decoded is not None:
        content, c_type, _ = decoded

    # 校验 MIME 类型，仅允许合法图片类型，阻止返回 text/html 等脚本内容造成同源反射执行
    clean_type = (c_type or "image/jpeg").split(";")[0].strip().lower()
    allowed_types = {
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "image/x-icon", "image/vnd.microsoft.icon", "image/bmp",
        "image/avif", "image/tiff", "image/svg+xml", "image/apng",
    }
    if clean_type not in allowed_types:
        raise ValueError(f"上游返回非图片格式: {clean_type}")

    # 防御同源 SVG 包含脚本等活跃内容造成的 XSS 攻击
    if clean_type == "image/svg+xml":
        lower_content = content[:32768].lower()
        if any(d in lower_content for d in (b"<script", b"onload=", b"onerror=", b"onclick=", b"javascript:", b"<foreignobject", b"<iframe")):
            raise ValueError("拒绝包含可执行脚本或危险标记的 SVG 图像")

    # 3. 异步/即时落盘（必须显式开启磁盘缓存时才写盘）
    if cfg.disk_cache_enabled:
        try:
            data_file.write_bytes(content)
            meta_file.write_text(c_type, encoding="utf-8")
        except Exception:
            pass

    return content, c_type, etag
