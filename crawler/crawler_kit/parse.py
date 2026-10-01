"""HTML 解析与选择器（零第三方依赖）。

为什么自己写：硬约束是"爬虫只能 import crawler_kit + 标准库"，
所以用不了 parsel/lxml。这里实现一个**够用的 CSS 子集**：

* 支持 ``tag``、``.class``、``#id``、``tag.class``、``*``
* 支持 ``[attr]``、``[attr=v]``、``[attr^=v]``、``[attr$=v]``、``[attr*=v]``、``[attr~=v]``
* 支持后代（空格）与子代（``>``）

不支持：伪类、伪元素、兄弟选择器（``+`` / ``~``）。
够不到的场景请直接用 :func:`re_first` / :func:`re_all` —— 例如 m3u8 地址
常常埋在 ``<script>`` 里的 JSON 字符串中，用选择器反而绕远路。
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from .clean import collapse, dedupe, is_placeholder_image, unescape_js

VOID_TAGS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)

#: 这些标签允许不写结束标签，遇到同类开始标签时要自动闭合栈顶
_IMPLIED_CLOSE = {
    "li": {"li"},
    "p": {"p"},
    "td": {"td", "th"},
    "th": {"td", "th"},
    "tr": {"tr"},
    "option": {"option"},
    "dt": {"dt", "dd"},
    "dd": {"dt", "dd"},
}

_COMPOUND_RE = re.compile(r"^(?P<tag>[a-zA-Z][\w-]*|\*)?(?P<rest>(?:[#.][\w-]+|\[[^\]]*\])*)$")
_ATTR_RE = re.compile(
    r"\[(?P<name>[\w:-]+)"
    r"(?:\s*(?P<op>[~^$*|]?=)\s*(?P<val>\"[^\"]*\"|'[^']*'|[^\]]*))?\]"
)
_PART_RE = re.compile(r"([#.][\w-]+|\[[^\]]*\])")


class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "data")

    def __init__(self, tag, attrs=None, parent=None, data=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.parent = parent
        self.data = data

    # ------------------------------------------------------------- 基本属性

    @property
    def is_text(self) -> bool:
        return self.tag == "#text"

    @property
    def class_list(self):
        return (self.attrs.get("class") or "").split()

    @property
    def is_hidden(self) -> bool:
        """行内样式隐藏，或带 ``hidden`` 属性。

        ncat21 的卡片里藏了两个 ``display:none`` 的广告水印同名节点，
        不过滤就会把广告当成影片名。
        """
        if "hidden" in self.attrs:
            return True
        style = (self.attrs.get("style") or "").replace(" ", "").lower()
        return "display:none" in style or "visibility:hidden" in style

    def attr(self, name, default=None):
        return self.attrs.get(name, default)

    @property
    def text(self) -> str:
        chunks = []
        self._collect_text(chunks)
        return collapse(" ".join(chunks))

    def _collect_text(self, out) -> None:
        for child in self.children:
            if child.is_text:
                out.append(child.data or "")
            else:
                child._collect_text(out)
                out.append(" ")

    # ------------------------------------------------------------- 查找

    def select(self, css, limit=None):
        return select(self, css, limit=limit)

    def select_one(self, css):
        found = select(self, css, limit=1)
        return found[0] if found else None

    select_first = select_one

    def __repr__(self):  # pragma: no cover - 调试用
        return f"<Node {self.tag} {self.attrs}>"


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self._stack = [self.root]

    @staticmethod
    def _attrs(attrs):
        return {key.lower(): (value if value is not None else "") for key, value in attrs}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        implied = _IMPLIED_CLOSE.get(tag)
        if implied:
            while len(self._stack) > 1 and self._stack[-1].tag in implied:
                self._stack.pop()
        parent = self._stack[-1]
        node = Node(tag, self._attrs(attrs), parent)
        parent.children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        parent = self._stack[-1]
        parent.children.append(Node(tag.lower(), self._attrs(attrs), parent))

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data):
        if data:
            parent = self._stack[-1]
            parent.children.append(Node("#text", None, parent, data))


def parse_html(source) -> Node:
    """把 HTML 字符串解析成节点树。传入 ``Node`` 时原样返回。"""
    if isinstance(source, Node):
        return source
    builder = _Builder()
    builder.feed(source or "")
    builder.close()
    return builder.root


# ------------------------------------------------------------------ 选择器


def _parse_compound(text):
    match = _COMPOUND_RE.match(text)
    if not match:
        return None
    selector = {"tag": match.group("tag"), "id": None, "classes": [], "attrs": []}
    for part in _PART_RE.findall(match.group("rest") or ""):
        if part.startswith("#"):
            selector["id"] = part[1:]
        elif part.startswith("."):
            selector["classes"].append(part[1:])
        else:
            attr_match = _ATTR_RE.match(part)
            if not attr_match:
                return None
            value = attr_match.group("val")
            if value is not None:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
            selector["attrs"].append(
                (attr_match.group("name").lower(), attr_match.group("op"), value)
            )
    return selector


def _split_selector(css):
    """把 ``a.b > c d`` 拆成 ``[(None, 'a.b'), ('>', 'c'), (' ', 'd')]``。"""
    parts = []
    buffer = ""
    pending = None
    depth = 0
    for char in (css or "").strip():
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)

        if depth == 0 and char == ">":
            if buffer.strip():
                parts.append((pending, buffer.strip()))
                buffer = ""
            pending = ">"
            continue
        if depth == 0 and char.isspace():
            if buffer.strip():
                parts.append((pending, buffer.strip()))
                buffer = ""
                pending = " "
            continue
        buffer += char

    if buffer.strip():
        parts.append((pending, buffer.strip()))
    if parts:
        parts[0] = (None, parts[0][1])
    return parts


def _descendants(node):
    out = []
    stack = list(reversed(node.children))
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(reversed(current.children))
    return out


def _matches(node, compound) -> bool:
    if node.is_text:
        return False
    selector = _parse_compound(compound)
    if selector is None:
        return False

    tag = selector["tag"]
    if tag and tag != "*" and node.tag != tag:
        return False
    if selector["id"] and node.attrs.get("id") != selector["id"]:
        return False
    if selector["classes"]:
        node_classes = node.class_list
        for name in selector["classes"]:
            if name not in node_classes:
                return False
    for name, op, value in selector["attrs"]:
        current = node.attrs.get(name)
        if current is None:
            return False
        if op is None:
            continue
        current = str(current)
        if op == "=" and current != value:
            return False
        if op == "^=" and not current.startswith(value):
            return False
        if op == "$=" and not current.endswith(value):
            return False
        if op == "*=" and value not in current:
            return False
        if op == "~=" and value not in current.split():
            return False
    return True


def select(root, css, limit=None):
    """在 ``root``（HTML 字符串或 :class:`Node`）里按 CSS 选择器找节点。"""
    node_root = parse_html(root)
    parts = _split_selector(css)
    if not parts:
        return []

    current = [node_root]
    for combinator, compound in parts:
        matches = []
        seen = set()
        for base in current:
            if combinator == ">":
                candidates = [c for c in base.children if not c.is_text]
            else:
                candidates = _descendants(base)
            for candidate in candidates:
                if id(candidate) in seen:
                    continue
                if _matches(candidate, compound):
                    seen.add(id(candidate))
                    matches.append(candidate)
        current = matches
        if not current:
            break

    return current[:limit] if limit is not None else current


def select_one(root, css):
    found = select(root, css, limit=1)
    return found[0] if found else None


def select_visible(root, css, limit=None):
    """只要没被行内样式隐藏的节点。"""
    return [node for node in select(root, css) if not node.is_hidden][:limit]


def visible(nodes):
    return [node for node in nodes if not node.is_hidden]


def first_image(node, attributes=("data-original", "data-src", "data-lazy-src", "data-echo", "src")):
    """取第一张「真」图。

    懒加载列表页常见做法是 ``<img src="占位图" data-original="真图">``，
    甚至同时放两个 ``<img>``。所以必须按属性优先级 + 占位图特征双重过滤。
    """
    for image in select(node, "img"):
        for name in attributes:
            url = image.attr(name)
            if url and not is_placeholder_image(url):
                return url
    return ""


# -------------------------------------------------------------- 正则工具

_MEDIA_RE = re.compile(
    r"""(?P<url>(?:https?:)?//[^\s"'<>\\]+?\.(?:m3u8|mp4)(?:\?[^\s"'<>\\]*)?)""",
    re.I,
)
_BARE_MEDIA_RE = re.compile(
    r"""(?P<url>[0-9a-zA-Z][\w.\-]*:\d{2,5}/[^\s"'<>\\]*?\.(?:m3u8|mp4)(?:\?[^\s"'<>\\]*)?)""",
    re.I,
)


def re_first(pattern, text, group=1, default=None, flags=re.I | re.S):
    if not text:
        return default
    if isinstance(pattern, str):
        pattern = re.compile(pattern, flags)
    match = pattern.search(text)
    if not match:
        return default
    try:
        value = match.group(group)
    except IndexError:
        return default
    return default if value is None else value


def re_all(pattern, text, group=1, flags=re.I | re.S):
    if not text:
        return []
    if isinstance(pattern, str):
        pattern = re.compile(pattern, flags)
    out = []
    for match in pattern.finditer(text):
        try:
            value = match.group(group)
        except IndexError:
            continue
        if value is not None:
            out.append(value)
    return out


def find_media_urls(text, extensions=("m3u8", "mp4"), include_bare=True):
    """从整段 HTML/JS 里抠出媒体地址。

    这一条是给"播放地址藏在 ``<script>`` 里"的站点准备的
    —— 那种情况下没有任何可依赖的选择器结构。
    """
    if not text:
        return []
    haystack = unescape_js(text)
    found = [m.group("url") for m in _MEDIA_RE.finditer(haystack)]
    if include_bare:
        found.extend(m.group("url") for m in _BARE_MEDIA_RE.finditer(haystack))

    wanted = tuple(ext.lower().lstrip(".") for ext in extensions)
    out = []
    for url in found:
        base = url.split("?", 1)[0].split("#", 1)[0].lower()
        if any(base.endswith("." + ext) for ext in wanted):
            out.append(url)

    out = dedupe(out)
    if include_bare:
        # 裸 host:port 形式若已被带协议的完整地址包含，就丢弃，避免同一地址出两条
        out = [
            url
            for url in out
            if url.startswith(("http://", "https://", "//"))
            or not any(url != other and url in other for other in out)
        ]
    return out


def find_m3u8(text):
    """只找 m3u8（最常见的播放地址形态）。"""
    return find_media_urls(text, extensions=("m3u8",))
