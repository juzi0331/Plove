"""HTML 解析与数据抽取器（纯 Python 零依赖）。

支持：
1. CSS 子集选择器：tag, .class, #id, tag.class, [attr], [attr=v], [attr*=v], [attr^=v], [attr$=v]
2. 后代选择器（空格）、子代选择器（>）
3. 属性提取（href, src, data-src 等）或 innerText 提取
4. 捕获组正则二次提纯
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Optional

from .models import FieldExtractor
from ..core.cleaner import collapse_whitespace, safe_resolve_url

VOID_TAGS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)

_ATTR_RE = re.compile(
    r"\[(?P<name>[\w:-]+)"
    r"(?:\s*(?P<op>[~^$*|]?=)\s*(?P<val>\"[^\"]*\"|'[^']*'|[^\]]*))?\]"
)
_PART_RE = re.compile(r"([#.][\w-]+|\[[^\]]*\])")
_COMPOUND_RE = re.compile(r"^(?P<tag>[a-zA-Z][\w-]*|\*)?(?P<rest>(?:[#.][\w-]+|\[[^\]]*\])*)$")


class HtmlNode:
    """轻量级 DOM 节点。"""

    __slots__ = ("tag", "attrs", "children", "parent", "data")

    def __init__(
        self,
        tag: str,
        attrs: Optional[dict[str, str]] = None,
        parent: Optional["HtmlNode"] = None,
        data: Optional[str] = None,
    ) -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[HtmlNode] = []
        self.parent = parent
        self.data = data

    @property
    def is_text(self) -> bool:
        return self.tag == "#text"

    @property
    def text(self) -> str:
        """递归提取全部子节点合并文本。"""
        if self.is_text:
            return self.data or ""
        out: list[str] = []
        for child in self.children:
            txt = child.text
            if txt:
                out.append(txt)
        return "".join(out)

    def attr(self, name: str, default: str = "") -> str:
        return self.attrs.get(name.lower(), default)

    def select(self, selector: str) -> list["HtmlNode"]:
        """按 CSS 选择器匹配后代节点。"""
        tokens = _tokenize_selector(selector)
        current = [self]
        for combinator, step in tokens:
            next_nodes: list[HtmlNode] = []
            for node in current:
                candidates = node.children if combinator == ">" else _collect_descendants(node)
                for cand in candidates:
                    if not cand.is_text and _match_step(cand, step):
                        next_nodes.append(cand)
            # 去重但保持顺序
            seen = set()
            deduped = []
            for n in next_nodes:
                nid = id(n)
                if nid not in seen:
                    seen.add(nid)
                    deduped.append(n)
            current = deduped
        return current

    def select_first(self, selector: str) -> Optional["HtmlNode"]:
        res = self.select(selector)
        return res[0] if res else None


def _collect_descendants(node: HtmlNode) -> list[HtmlNode]:
    result: list[HtmlNode] = []
    for c in node.children:
        result.append(c)
        if c.children:
            result.extend(_collect_descendants(c))
    return result


def _tokenize_selector(selector: str) -> list[tuple[str, str]]:
    cleaned = re.sub(r"\s*([>])\s*", r" \1 ", selector.strip())
    parts = cleaned.split()
    tokens: list[tuple[str, str]] = []
    prev_comb = ""
    for part in parts:
        if part == ">":
            prev_comb = ">"
        else:
            tokens.append((prev_comb or " ", part))
            prev_comb = ""
    return tokens


def _match_step(node: HtmlNode, step: str) -> bool:
    m = _COMPOUND_RE.match(step)
    if not m:
        return False
    tag = m.group("tag")
    if tag and tag != "*" and node.tag.lower() != tag.lower():
        return False
    rest = m.group("rest") or ""
    for part in _PART_RE.findall(rest):
        if part.startswith("."):
            cls = part[1:].lower()
            node_classes = [c.lower() for c in node.attr("class").split()]
            if cls not in node_classes:
                return False
        elif part.startswith("#"):
            if node.attr("id") != part[1:]:
                return False
        elif part.startswith("["):
            am = _ATTR_RE.match(part)
            if not am:
                return False
            aname = am.group("name").lower()
            if aname not in node.attrs:
                return False
            op = am.group("op")
            if not op:
                continue
            val = (am.group("val") or "").strip("'\"")
            node_val = node.attrs[aname]
            if op == "=" and node_val != val:
                return False
            if op == "*=" and val not in node_val:
                return False
            if op == "^=" and not node_val.startswith(val):
                return False
            if op == "$=" and not node_val.endswith(val):
                return False
    return True


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("#root")
        self.stack: list[HtmlNode] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        parent = self.stack[-1]
        node = HtmlNode(tag.lower(), attr_dict, parent=parent)
        parent.children.append(node)
        if tag.lower() not in VOID_TAGS:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        for idx in range(len(self.stack) - 1, 0, -1):
            if self.stack[idx].tag == tag_l:
                self.stack = self.stack[:idx]
                break

    def handle_data(self, data: str) -> None:
        if not data:
            return
        parent = self.stack[-1]
        parent.children.append(HtmlNode("#text", parent=parent, data=data))


def parse_html(html_content: str) -> HtmlNode:
    """构建 HTML 树。"""
    builder = _TreeBuilder()
    builder.feed(html_content or "")
    return builder.root


def extract_html_field(
    node: HtmlNode,
    rule: FieldExtractor,
    base_url: str = "",
    full_html_text: str = "",
) -> str:
    """根据抽取规则从节点或全文抽取单个字段值。"""
    raw_val = ""

    if rule.type == "constant":
        return rule.default or ""

    if rule.type == "regex":
        search_target = node.text if node else full_html_text
        if rule.regex:
            m = re.search(rule.regex, search_target)
            if m:
                try:
                    raw_val = m.group(rule.regex_group)
                except IndexError:
                    raw_val = m.group(0)
            else:
                raw_val = rule.default or ""

    else:
        # CSS 选择器模式
        target_node = node
        if rule.selector:
            target_node = node.select_first(rule.selector)

        if target_node:
            if rule.attribute:
                raw_val = target_node.attr(rule.attribute, "")
                if rule.attribute.lower() in ("href", "src", "data-src", "data-original") and base_url:
                    raw_val = safe_resolve_url(base_url, raw_val)
            else:
                raw_val = target_node.text

        # 如果配置了二次正则
        if raw_val and rule.regex:
            m = re.search(rule.regex, raw_val)
            if m:
                try:
                    raw_val = m.group(rule.regex_group)
                except IndexError:
                    raw_val = m.group(0)
            else:
                raw_val = rule.default or ""

    if not raw_val and rule.default:
        raw_val = rule.default

    if rule.template and raw_val:
        raw_val = rule.template.format(value=raw_val)

    if rule.strip:
        raw_val = collapse_whitespace(raw_val)

    return raw_val
