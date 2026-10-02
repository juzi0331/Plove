"""图片防盗链代理与持久化缓存服务。

针对第三方图床/源站（如部分 m3u8 海报）开启防盗链限制、报 403 Forbidden 或跨域失败的问题：
1. 伪造 Referer 与 User-Agent 发起代理抓取；
2. 服务端本地持久化缓存（基于 URL SHA256 哈希），避免重复向源站发请求被限速；
3. 支持 HTTP ETag / 304 协商缓存，提升前端访问速度；
4. 提供缓存占用大小统计与一键清理能力。
"""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.clock import utcnow
from app.core.config import BACKEND_DIR
from app.db.session import commit_now
from app.models.system_setting import SystemSetting
from app.schemas.admin_extended import ImageProxyClearResult, ImageProxyConfig, ImageProxyStats

CACHE_DIR = BACKEND_DIR / "data" / "img_cache"
PROXY_CONFIG_KEY = "image_proxy_config"

# 注入爬虫目录以便动态加载各站点适配器解密钩子
_crawler_dir = Path(__file__).resolve().parents[3] / "crawler"
if _crawler_dir.is_dir() and str(_crawler_dir) not in sys.path:
    sys.path.insert(0, str(_crawler_dir))

# 内存缓存站点解码器映射表 {site_key: decoder_callable}
_site_decoders: dict[str, Any] = {}


def _get_site_decoder(site_key: str) -> Any | None:
    """获取指定站点的图片解码器（如果有的话）。"""
    if site_key in _site_decoders:
        return _site_decoders[site_key]
    try:
        mod = importlib.import_module(f"sites.{site_key}")
        decoder = getattr(mod, "decode_image", None)
        if decoder is None:
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if isinstance(attr, type) and hasattr(attr, "decode_image"):
                    decoder = getattr(attr, "decode_image")
                    break
        _site_decoders[site_key] = decoder
        return decoder
    except Exception:
        _site_decoders[site_key] = None
        return None


def _decode_image_via_sites(content: bytes, site: str | None = None) -> tuple[bytes, str] | None:
    """尝试通过站点插件解码加密图片。

    1. 若指定 site，优先调用该 site 的 decode_image 插件方法；
    2. 若未指定 site 或指定站点未能成功解密，且 content 不是标准图片格式，
       自动扫描探测其它站点插件尝试解密。
    """
    if not content or len(content) < 16:
        return None
    # 已经是标准图片格式（JPEG, PNG, WEBP, GIF），无需解密
    if (
        content.startswith(b"\xff\xd8\xff")
        or content.startswith(b"\x89PNG")
        or content.startswith(b"RIFF")
        or content.startswith(b"GIF8")
    ):
        return None

    # 1. 尝试指定站点
    if site:
        decoder = _get_site_decoder(site)
        if callable(decoder):
            try:
                res = decoder(content)
                if res and isinstance(res, tuple) and len(res) == 2:
                    return res
            except Exception:
                pass

    # 2. 自动探测：扫描 sites/ 目录下所有实现了 decode_image 的站点
    sites_dir = _crawler_dir / "sites"
    if sites_dir.is_dir():
        for file in sites_dir.glob("*.py"):
            site_key = file.stem
            if site_key.startswith("_") or site_key == site:
                continue
            decoder = _get_site_decoder(site_key)
            if callable(decoder):
                try:
                    res = decoder(content)
                    if res and isinstance(res, tuple) and len(res) == 2:
                        return res
                except Exception:
                    pass

    return None


_cached_config: ImageProxyConfig | None = None



def get_image_proxy_config(db: Any = None) -> ImageProxyConfig:
    global _cached_config
    if _cached_config is not None:
        return _cached_config
    if db is None:
        from app.db.session import get_session_factory
        with get_session_factory()() as session:
            return get_image_proxy_config(session)
    row = db.query(SystemSetting).filter_by(key=PROXY_CONFIG_KEY).first()
    if not row or not row.value_json:
        _cached_config = ImageProxyConfig()
        return _cached_config
    try:
        data = json.loads(row.value_json)
        _cached_config = ImageProxyConfig(**data)
        return _cached_config
    except Exception:
        _cached_config = ImageProxyConfig()
        return _cached_config


def update_image_proxy_config(db: Any, payload: ImageProxyConfig) -> ImageProxyConfig:
    global _cached_config
    payload.updated_at = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = db.query(SystemSetting).filter_by(key=PROXY_CONFIG_KEY).first()
    if not row:
        row = SystemSetting(key=PROXY_CONFIG_KEY, value_json=payload.model_dump_json())
        db.add(row)
    else:
        row.value_json = payload.model_dump_json()
    commit_now(db)
    _cached_config = payload
    return payload


def is_global_image_proxy_enabled() -> bool:
    cfg = get_image_proxy_config()
    return cfg.global_proxy_enabled


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
    site: str | None = None,
) -> tuple[bytes, str, str]:
    """获取图片内容，返回 (二进制数据, Content-Type, ETag)。"""
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

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"源站返回 HTTP {resp.status_code}")
        
        content = resp.content
        c_type = resp.headers.get("content-type", "image/jpeg")

    # 委托对应站点适配器（或探测站点插件）解码可能加密的图片格式
    decoded = _decode_image_via_sites(content, site=site)
    if decoded is not None:
        content, c_type = decoded


    # 3. 异步/即时落盘（必须显式开启磁盘缓存时才写盘）
    if cfg.disk_cache_enabled:
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
