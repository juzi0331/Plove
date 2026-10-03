"""数据清洗：URL 归一化、文本去噪、数字解析、广告域名过滤。

这些逻辑原本散落在每个适配器里（参考项目就是那样），
这里只保留一份，站点文件才能写得短。
"""

from __future__ import annotations

import html as _html
import re
import urllib.parse

_TAG_RE = re.compile(r"<[^>]+>")

#: 裸 host:port 开头的地址（ncat21 的 m3u8 就是这种）
_BARE_HOST_RE = re.compile(r"^[0-9a-zA-Z][\w.\-]*:\d{2,5}/")

#: 占位图/图标特征。不排掉它们，列表页的封面会全是 logo
_PLACEHOLDER_RE = re.compile(
    r"placeholder|spacer|blank|transparent|default_cover|loading"
    r"|/logo|favicon|avatar|qrcode|arrow|close|\.svg(?:$|\?)|noneCover",
    re.I,
)
_WS_RE = re.compile(r"[\s\u3000]+")
_INT_RE = re.compile(r"-?\d+")
_FLOAT_RE = re.compile(r"-?\d+(?:\.\d+)?")
_QUALITY_RE = re.compile(
    r"(\d{3,4}\s*[pP]|4[kK]|8[kK]|蓝光|高清|超清|标清|HD国语|国语|粤语|TC|HD|SD)"
)

#: 页面底部常见推广/导航站域名，采集时应丢弃
DEFAULT_BLOCKED_HOSTS = (
    "t.me",
    "telegram.me",
    "telegram.org",
    "baidu.com",
    "googletagmanager.com",
    "google-analytics.com",
    "doubleclick.net",
)

#: 引流话术，出现在简介/标题里就说明抓错了地方
DEFAULT_PROMO_KEYWORDS = (
    "免费观看",
    "永久地址",
    "发布页",
    "备用网址",
    "加群",
    "防走失",
    "点击进入",
    "立即下载",
    "下载APP",
    "商务合作",
)


def absolute(url: str, base: str = "") -> str:
    """相对 URL 转绝对 URL。``//host/x`` 这种协议相对形式也会补全。"""
    if not url:
        return ""
    url = str(url).strip()
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("data:"):
        return url
    # 裸 host:port 形式：urljoin 会把它当成相对路径拼错，必须先补协议
    if _BARE_HOST_RE.match(url):
        return "https://" + url
    if not base:
        return url
    return urllib.parse.urljoin(base.rstrip("/") + "/", url)


def safe_relative_path(value) -> str:
    """把上层传下来的定位符收敛成一个**站内相对路径**；不合规就返回空串。

    为什么必须有这一步：``play_id`` 这类值是**上层回传**的（后端/前端从详情里
    拿到再送回来），而站点适配器会拿它直接去 ``fetch``。一个绝对 URL 就能让
    爬虫变成"任意地址的抓取代理"（SSRF），而且抓回来的东西还会当成播放地址
    往外吐。

    拒绝三种最经典的绕过：

    * ``https://evil.com/x`` —— 带协议，会被当成绝对 URL；
    * ``//evil.com/x`` —— **协议相对**，拼上 base 之后主机就被换掉了
      （只检查 "以 / 开头" 会正好把它放过去）；
    * 含反斜杠的 —— Windows 与部分解析器会把 ``\\`` 当成 ``/``；
    * 带 ``..`` 段的 —— 一个真正的播放地址里不会出现它，出现就说明有人在试探。

    返回空串而不是抛异常：调用方通常能退回一条更慢但同样正确的路径，
    没必要因为一个畸形的值让用户看不了片。
    """
    text = str(value or "").strip()
    if not text.startswith("/") or text.startswith("//"):
        return ""
    if "\\" in text or "://" in text:
        return ""
    if any(segment == ".." for segment in text.split("/")):
        return ""
    return text


def is_placeholder_image(url: str) -> bool:
    """判断是不是占位图/图标。列表页封面经常混着 logo 和真图。"""
    if not url:
        return True
    return bool(_PLACEHOLDER_RE.search(str(url)))


def unescape(text: str) -> str:
    return _html.unescape(text or "")


def unescape_js(text: str) -> str:
    """反转 JS 字符串里常见的转义，便于正则去抠 m3u8。

    ⚠️ **这里绝对不能用 ``html.unescape()``。**
    HTML5 允许命名实体省略末尾分号，于是 ``&timestamp=`` 会被解成 ``×tamp=``
    （``&times`` -> ``×``）—— 播放地址当场静默失效，而且不报任何错。
    所以只做精确替换：JS 的转义序列 + 唯一合法出现在 URL 里的 ``&amp;``。
    """
    if not text:
        return ""
    text = text.replace("\\u002F", "/").replace("\\u002f", "/")
    text = text.replace("\\u003A", ":").replace("\\u003a", ":")
    return text.replace("\\/", "/").replace("&amp;", "&")


def strip_tags(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    return _TAG_RE.sub(" ", text)


def collapse(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def clean_text(text: str) -> str:
    """去标签 + 反转义 + 收空白，简称"洗干净"。"""
    return collapse(unescape(strip_tags(text)))


def to_int(value, default=None):
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = _INT_RE.search(str(value))
    return int(match.group()) if match else default


def to_float(value, default=None):
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    match = _FLOAT_RE.search(str(value))
    return float(match.group()) if match else default


def normalize_quality(text: str) -> str:
    """把画质标签归一化，例如 ``hd国语`` -> ``HD国语``，``1080p`` -> ``1080P``。"""
    text = collapse(text)
    if not text:
        return ""
    match = _QUALITY_RE.search(text)
    if not match:
        return text
    token = match.group(1)
    return token.upper() if re.fullmatch(r"\d{3,4}\s*[pP]", token) else token


#: Unicode 变体字母：数学粗斜体/花体（U+1D400–U+1D7FF）+ 全角字母数字
_VARIANT_CHARS = "\\U0001D400-\\U0001D7FF\uFF10-\uFF19\uFF21-\uFF3A\uFF41-\uFF5A"
_DECORATED_TOKEN_RE = re.compile("[^\\s]*[" + _VARIANT_CHARS + "][^\\s]*")


def strip_decorated(text: str) -> str:
    """删掉用 Unicode 变体字母伪装的引流域名。

    实测样本（ncat21 详情页标题）：

        𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞 最糟糕的初恋 𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞

    ``𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞`` 是真域名 ``kkys01.com`` 的数学粗体写法，
    关键词匹配完全抳不到。只能按字符区间整块删 —— 而且只删
    "含有变体字符的那个词"，不碰其他内容（所以它不会误伤正常标题）。
    """
    if not text:
        return ""
    return collapse(_DECORATED_TOKEN_RE.sub(" ", str(text)))


def strip_promo(text: str, keywords=None) -> str:
    """去掉简介/标题里的引流话术与变体字域名。"""
    text = strip_decorated(collapse(text))
    if not text:
        return ""
    for word in keywords or DEFAULT_PROMO_KEYWORDS:
        text = text.replace(word, " ")
    return collapse(text)


clean_title = strip_promo


def is_blocked_host(url: str, blocked=None) -> bool:
    if not url:
        return True
    host = urllib.parse.urlsplit(url).hostname or ""
    host = host.lower()
    return any(host == h or host.endswith("." + h) for h in (blocked or DEFAULT_BLOCKED_HOSTS))


def dedupe(seq, key=lambda item: item):
    """按 key 去重并保持原顺序。"""
    seen = set()
    out = []
    for item in seq:
        marker = key(item)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out
