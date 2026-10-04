"""图片解密调度链与站点解码器适配。"""

from __future__ import annotations

import base64
import importlib
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.security import is_safe_public_url
from app.schemas.admin_extended import (
    ImageDecryptionRule,
    TestDecryptResult,
)
from app.services.image_proxy.config import get_image_proxy_config


# 注入爬虫目录以便动态加载各站点适配器解密钩子
def _get_crawler_sites_dir() -> Path:
    try:
        from app.core.config import get_settings
        c_dir = get_settings().sites_dir
        if c_dir.is_dir():
            return c_dir
    except Exception:
        pass
    fallback = Path(__file__).resolve().parents[4] / "crawler" / "sites"
    return fallback


_crawler_sites_dir = _get_crawler_sites_dir()
_crawler_base_dir = _crawler_sites_dir.parent
if _crawler_base_dir.is_dir() and str(_crawler_base_dir) not in sys.path:
    sys.path.insert(0, str(_crawler_base_dir))

# 内存缓存站点解码器映射表 {site_key: decoder_callable}
_site_decoders: dict[str, Any] = {}


def _decrypt_with_rule(content: bytes, rule: ImageDecryptionRule) -> tuple[bytes, str] | None:
    """根据自定义规则执行 AES 解密，成功返回 (plain_bytes, mime_type)。"""
    if not content or len(content) < 16 or len(content) % 16 != 0:
        return None
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except Exception:
        return None

    try:
        raw_key = (rule.key or "").strip()
        raw_iv = (rule.iv or "").strip()
        if not raw_key:
            return None

        if rule.is_hex:
            key_bytes = bytes.fromhex(raw_key)
            iv_bytes = bytes.fromhex(raw_iv) if raw_iv else b""
        else:
            key_bytes = raw_key.encode("utf-8")
            iv_bytes = raw_iv.encode("utf-8") if raw_iv else b""

        if rule.algorithm == "AES-128-ECB":
            mode_obj = modes.ECB()
        else:
            if len(iv_bytes) != 16:
                return None
            mode_obj = modes.CBC(iv_bytes)

        cipher = Cipher(algorithms.AES(key_bytes), mode_obj)
        decryptor = cipher.decryptor()
        plain = decryptor.update(content) + decryptor.finalize()

        for magic, mime in (
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"\x89PNG", "image/png"),
            (b"RIFF", "image/webp"),
            (b"GIF8", "image/gif"),
        ):
            if plain.startswith(magic):
                pad_len = plain[-1]
                if 1 <= pad_len <= 16 and plain[-pad_len:] == bytes([pad_len]) * pad_len:
                    plain = plain[:-pad_len]
                return plain, mime
    except Exception:
        pass
    return None


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
    """尝试通过站点插件解码加密图片。"""
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
    sites_dir = _get_crawler_sites_dir()
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


def _decode_image_dynamic(
    content: bytes,
    url: str | None = None,
    site: str | None = None,
    specific_rule: ImageDecryptionRule | None = None,
) -> tuple[bytes, str, str | None] | None:
    """多级动态图片解密调度链：
    
    1. 若指定特定规则 specific_rule，优先用该规则解密；
    2. 读取后台已配置的 decryption_rules：
       a. 优先匹配图片域名 match_domains 的已启用规则；
       b. 其次匹配所属站点 site_key 的已启用规则；
       c. 尝试其它已启用规则；
    3. 若未命中或失败，调用站点插件代码里的 decode_image 钩子；
    4. 最后调用已知密钥库兜底。
    
    返回 (plain_bytes, mime_type, matched_rule_id) 或 None。
    """
    if not content or len(content) < 16:
        return None
    # 已经是标准图片，无需解密
    if (
        content.startswith(b"\xff\xd8\xff")
        or content.startswith(b"\x89PNG")
        or content.startswith(b"RIFF")
        or content.startswith(b"GIF8")
    ):
        return None

    # 1. 特定规则优先
    if specific_rule is not None:
        res = _decrypt_with_rule(content, specific_rule)
        if res:
            return res[0], res[1], specific_rule.id or "custom_rule"

    # 2. 读取后台配置规则
    cfg = get_image_proxy_config()
    rules = [r for r in cfg.decryption_rules if r.enabled]

    # 按优先级排序规则：域名匹配 > 站点匹配 > 其它通用规则
    parsed_domain = ""
    if url:
        try:
            parsed_domain = urlparse(url).netloc.lower()
        except Exception:
            pass

    domain_rules: list[ImageDecryptionRule] = []
    site_rules: list[ImageDecryptionRule] = []
    other_rules: list[ImageDecryptionRule] = []

    for r in rules:
        matched_domain = False
        if parsed_domain and r.match_domains:
            for d in r.match_domains:
                if d and d.lower() in parsed_domain:
                    matched_domain = True
                    break
        if matched_domain:
            domain_rules.append(r)
        elif site and r.site_key and r.site_key == site:
            site_rules.append(r)
        else:
            other_rules.append(r)

    sorted_rules = domain_rules + site_rules + other_rules
    for r in sorted_rules:
        res = _decrypt_with_rule(content, r)
        if res:
            return res[0], res[1], r.id

    # 3. 站点插件适配器解密
    site_res = _decode_image_via_sites(content, site=site)
    if site_res:
        return site_res[0], site_res[1], "site_adapter_plugin"

    return None


def test_decrypt_image(
    url: str,
    site_key: str = "",
    rule: ImageDecryptionRule | None = None,
) -> TestDecryptResult:
    """在后台实测解密任意加密图片链接，验证 Key/IV 与规则是否有效。"""
    start_t = time.perf_counter()

    url = (url or "").strip().strip("'\"`")
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith(("http://", "https://")) and "://" not in url:
        url = "https://" + url

    if not is_safe_public_url(url):
        return TestDecryptResult(
            success=False,
            message="图片链接不合规或指向受限的局域网/内网地址",
        )

    try:
        parsed = urlparse(url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": f"{parsed.scheme}://{parsed.netloc}/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                return TestDecryptResult(
                    success=False,
                    message=f"从源站抓取测试图片失败: HTTP {resp.status_code}",
                )
            raw_content = resp.content
    except Exception as exc:
        return TestDecryptResult(
            success=False,
            message=f"请求源站图片异常: {exc}",
        )

    elapsed_temp = round((time.perf_counter() - start_t) * 1000, 2)
    if not raw_content or len(raw_content) == 0:
        return TestDecryptResult(
            success=False,
            message="从源站下载到的内容为空（0 字节）。目标图床可能开启了动态鉴权或链接缺少签名（例如缺少 ?auth_key=... 签名），请粘贴前台影片正在使用的有效完整封面链接进行测试。",
            size_bytes=0,
            elapsed_ms=elapsed_temp,
        )

    if len(raw_content) < 16:
        return TestDecryptResult(
            success=False,
            message=f"从源站获取到的数据过短（仅 {len(raw_content)} 字节），非有效图片或密文数据。",
            size_bytes=len(raw_content),
            elapsed_ms=elapsed_temp,
        )

    # 尝试解密
    matched_id = None
    decoded = None
    if rule is not None:
        res = _decrypt_with_rule(raw_content, rule)
        if res:
            decoded = res
            matched_id = rule.id or "custom_rule"

    if decoded is None:
        res_dyn = _decode_image_dynamic(raw_content, url=url, site=site_key, specific_rule=rule)
        if res_dyn:
            decoded = (res_dyn[0], res_dyn[1])
            matched_id = res_dyn[2]

    elapsed = round((time.perf_counter() - start_t) * 1000, 2)

    if decoded is not None:
        content_bytes, mime_type = decoded
        b64 = base64.b64encode(content_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"
        return TestDecryptResult(
            success=True,
            message=f"解密成功！匹配规则 [{matched_id or '规则匹配'}]，格式: {mime_type.split('/')[-1].upper()}，耗时 {elapsed}ms",
            matched_rule_id=matched_id,
            mime_type=mime_type,
            size_bytes=len(content_bytes),
            elapsed_ms=elapsed,
            preview_data_url=data_url,
        )

    # 若无需解密就是正常图片
    for magic, mime in (
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG", "image/png"),
        (b"RIFF", "image/webp"),
        (b"GIF8", "image/gif"),
    ):
        if raw_content.startswith(magic):
            b64 = base64.b64encode(raw_content).decode("ascii")
            return TestDecryptResult(
                success=True,
                message=f"该图片无需解密，源站返回的本身即为标准图片（{mime}）",
                mime_type=mime,
                size_bytes=len(raw_content),
                elapsed_ms=elapsed,
                preview_data_url=f"data:{mime};base64,{b64}",
            )

    return TestDecryptResult(
        success=False,
        message=f"解密未成功：提供的密钥无法将此二进制数据解密为合法的图片格式（前 16 字节: {raw_content[:16].hex()}）",
        size_bytes=len(raw_content),
        elapsed_ms=elapsed,
    )
