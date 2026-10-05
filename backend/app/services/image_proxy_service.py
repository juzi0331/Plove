"""图片防盗链代理与持久化缓存服务。

针对第三方图床/源站（如部分 m3u8 海报）开启防盗链限制、报 403 Forbidden 或跨域失败的问题：
1. 伪造 Referer 与 User-Agent 发起代理抓取；
2. 服务端本地持久化缓存（基于 URL SHA256 哈希），避免重复向源站发请求被限速；
3. 支持 HTTP ETag / 304 协商缓存，提升前端访问速度；
4. 提供缓存占用大小统计与一键清理能力。
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import BACKEND_DIR
from app.schemas.admin_extended import ImageProxyClearResult, ImageProxyStats

CACHE_DIR = BACKEND_DIR / "data" / "img_cache"

_CDND_COOKIE = "cdndefend_js_cookie"
_CDND_STATUS = 850
_CDND_SECRET_RE = re.compile(r"['\"]([0-9A-Fa-f]{40})['\"]")
_NCAT_RDUL_HOSTS = (
    "https://103.39.111.180:51050",
    "https://103.39.111.184:51050",
)


def _solve_cdndefend(challenge_html: str) -> str:
    """Solve the lightweight cdndefend JS challenge used by ncat21 image hosts."""
    match = _CDND_SECRET_RE.search(challenge_html or "")
    if not match:
        raise RuntimeError("cdndefend challenge secret not found")
    secret = match.group(1).upper()
    offset = int(secret[0], 16)
    for counter in range(2_000_000):
        digest = hashlib.sha1(f"{secret}{counter}".encode()).digest()
        if digest[offset] == 0xB0 and digest[offset + 1] == 0x0B:
            return secret + str(counter)
    raise RuntimeError("cdndefend challenge solve timeout")


def ensure_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _is_safe_url(url: str) -> bool:
    """安全校验：仅允许公网 http / https，阻止探测内网主机。"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        if not hostname or hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        if hostname.startswith("192.168.") or hostname.startswith("10.") or hostname.startswith("172."):
            return False
        return True
    except Exception:
        return False


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def fetch_image_with_cache(
    url: str,
    custom_referer: str | None = None,
    timeout_seconds: float = 10.0,
) -> tuple[bytes, str, str]:
    """获取图片内容，返回 (二进制数据, Content-Type, ETag)。"""
    if not _is_safe_url(url):
        raise ValueError("不合规或受保护的图片地址")

    cdir = ensure_cache_dir()
    h = _hash_url(url)
    data_file = cdir / f"{h}.bin"
    meta_file = cdir / f"{h}.meta"

    etag = f'"{h}"'

    # 1. 检查本地磁盘持久化缓存
    if data_file.exists() and meta_file.exists():
        try:
            content = data_file.read_bytes()
            c_type = meta_file.read_text(encoding="utf-8").strip() or "image/jpeg"
            return content, c_type, etag
        except Exception:
            pass

    # 2. 远端抓取
    parsed = urlparse(url)
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

    hostname = (parsed.hostname or "").lower()
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        resp = None

        # 网飞猫网页里的 LazyImageLoader 本来就会把 /vod1/* 图片改到 RDUL
        # 资源节点；直接访问 www.ncat21.com 的图片反而会遭遇 850/403。
        # 后端代理复刻源站自己的正确取图路径，避免每张封面都跑一次挑战。
        if hostname.endswith("ncat21.com") and parsed.path.startswith("/vod1/"):
            suffix = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            for base in _NCAT_RDUL_HOSTS:
                try:
                    candidate = client.get(base + suffix, headers=headers)
                except httpx.HTTPError:
                    continue
                candidate_type = candidate.headers.get("content-type", "")
                if candidate.status_code == 200 and candidate_type.lower().startswith("image/"):
                    resp = candidate
                    break

        if resp is None:
            resp = client.get(url, headers=headers)

        # RDUL 全部不可用时保留 cdndefend 兜底。
        if resp.status_code == _CDND_STATUS and hostname.endswith("ncat21.com"):
            cookie_value = _solve_cdndefend(resp.text)
            time.sleep(1.05)
            headers_with_cookie = dict(headers)
            headers_with_cookie["Cookie"] = f"{_CDND_COOKIE}={cookie_value}"
            resp = client.get(url, headers=headers_with_cookie)

        if resp.status_code != 200:
            raise RuntimeError(f"源站返回 HTTP {resp.status_code}")

        content = resp.content
        c_type = resp.headers.get("content-type", "image/jpeg")
        if not c_type.lower().startswith("image/"):
            raise RuntimeError(f"源站返回的不是图片: {c_type}")

    # 3. 异步/即时落盘
    try:
        data_file.write_bytes(content)
        meta_file.write_text(c_type, encoding="utf-8")
    except Exception:
        pass

    return content, c_type, etag


def get_proxy_stats() -> ImageProxyStats:
    """统计图片代理缓存文件数量与占用空间大小。"""
    cdir = ensure_cache_dir()
    files = list(cdir.glob("*.bin"))
    total_bytes = sum(f.stat().st_size for f in files if f.is_file())
    total_mb = round(total_bytes / (1024 * 1024), 2)
    return ImageProxyStats(
        cached_files=len(files),
        total_size_mb=total_mb,
        cache_dir=str(cdir.resolve()),
    )


def clear_proxy_cache() -> ImageProxyClearResult:
    """清空图片代理缓存。"""
    cdir = ensure_cache_dir()
    stats = get_proxy_stats()
    try:
        shutil.rmtree(cdir)
        ensure_cache_dir()
    except Exception:
        pass
    return ImageProxyClearResult(
        cleared_files=stats.cached_files,
        freed_mb=stats.total_size_mb,
    )
