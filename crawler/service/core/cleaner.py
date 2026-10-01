"""数据清洗工具集。

吸收项目实战踩坑沉淀：
1. 变体字广告剥离（Unicode 数学粗体字符集）
2. 相对 URL 安全校验（防止 //evil.com 协议相对路径和跨域穿越）
3. 多余空白压缩与占位图过滤
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Iterable

# 匹配 Unicode 数学粗体/双线/斜体等常用作变体广告的字符区间
# 包含了常见仿粗体字母数字: 1D400-1D7FF 等
_DECORATED_PATTERN = re.compile(
    r"[\U0001D400-\U0001D7FF\U0000FF01-\U0000FF5E]+"
)

# 协议相对 URL 匹配
_PROTOCOL_RELATIVE_RE = re.compile(r"^//")


def collapse_whitespace(text: str | None) -> str:
    """压缩所有连续空白字符为单空格并去除首尾空白。"""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def strip_decorated_ad_words(text: str | None) -> str:
    """去除包含数学变体符号的广告词（按空格或边界整块移除）。"""
    if not text:
        return ""
    words = text.split()
    clean_words = []
    for w in words:
        if _DECORATED_PATTERN.search(w):
            continue
        clean_words.append(w)
    result = " ".join(clean_words)
    return collapse_whitespace(result)


def clean_title(title: str | None, ad_patterns: Iterable[str] | None = None) -> str:
    """全面清洗影片标题或分类名。"""
    if not title:
        return ""
    val = strip_decorated_ad_words(title)
    if ad_patterns:
        for pat in ad_patterns:
            try:
                val = re.sub(pat, "", val, flags=re.IGNORECASE)
            except re.error:
                continue
    return collapse_whitespace(val)


def safe_resolve_url(base_url: str, path_or_url: str | None) -> str:
    """安全地将站内相对路径拼装成合法完整 URL。

    - 已经是 http/https 绝对地址的直接返回；
    - 防止 //evil.com 协议相对地址跳脱；
    - 相对路径使用 urllib.parse.urljoin 规范化。
    """
    if not path_or_url:
        return ""
    val = path_or_url.strip()
    if not val:
        return ""

    if _PROTOCOL_RELATIVE_RE.match(val):
        # 协议相对 URL，补齐 base_url 的协议头
        parsed_base = urllib.parse.urlparse(base_url)
        scheme = parsed_base.scheme or "https"
        return f"{scheme}:{val}"

    if val.startswith("http://") or val.startswith("https://"):
        return val

    return urllib.parse.urljoin(base_url, val)


def is_placeholder_image(url: str | None) -> bool:
    """识别常见的占位图、错误海报或 1x1 透明图。"""
    if not url:
        return True
    lower = url.lower()
    placeholders = (
        "data:image/gif;base64,r0lgod",
        "placeholder",
        "no_pic",
        "nopic",
        "default_cover",
        "loading.gif",
        "empty.png",
    )
    return any(p in lower for p in placeholders)
