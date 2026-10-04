from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

_site_decoders: dict[str, Any] = {}
_crawler_dir = Path(__file__).resolve().parents[2]


def get_site_decoder(site_key: str) -> Any | None:
    """获取指定站点的图片解码钩子（如果实现的话）。"""
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


def decode_image_via_sites(content: bytes, site: str | None = None) -> tuple[bytes, str] | None:
    """尝试解码加密图片数据（委托站点插件自身的 decode_image 钩子）。"""
    if not content or len(content) < 16:
        return None
    # 已经是标准图片魔数无需解密
    if (
        content.startswith(b"\xff\xd8\xff")
        or content.startswith(b"\x89PNG")
        or content.startswith(b"RIFF")
        or content.startswith(b"GIF8")
    ):
        return None

    # 1. 优先指定站点
    if site:
        decoder = get_site_decoder(site)
        if callable(decoder):
            try:
                res = decoder(content)
                if res and isinstance(res, tuple) and len(res) == 2:
                    return res
            except Exception:
                pass

    # 2. 扫描 sites/ 目录下的所有站点插件探测解密
    sites_dir = _crawler_dir / "sites"
    if sites_dir.is_dir():
        for file in sites_dir.glob("*.py"):
            s_key = file.stem
            if s_key.startswith("_") or s_key == site:
                continue
            decoder = get_site_decoder(s_key)
            if callable(decoder):
                try:
                    res = decoder(content)
                    if res and isinstance(res, tuple) and len(res) == 2:
                        return res
                except Exception:
                    pass

    return None

