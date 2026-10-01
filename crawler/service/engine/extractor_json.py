"""JSON 数据抽取器（支持点分路径与列表展开）。

支持路径语法：
- "data.id" -> 访问 dict key
- "data.items" -> 获取列表
- "data.episodes[0].url" -> 访问索引
- "data.list[*].title" -> 通配列表所有条目
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .models import FieldExtractor
from ..core.cleaner import collapse_whitespace, safe_resolve_url

_INDEX_RE = re.compile(r"^([\w-]+)\[(\d+|\*)\]$")


def get_json_path_value(data: Any, path: str) -> Any:
    """按点分路径提取 JSON 内部对象。"""
    if not path or path == "." or path == "$":
        return data

    # 规范化：去除开头的 $. 或 /
    cleaned = path.lstrip("$./")
    parts = cleaned.split(".")

    current = data
    for part in parts:
        if current is None:
            return None

        # 检查是否包含 [index] 或 [*]
        m = _INDEX_RE.match(part)
        if m:
            key_name, idx_str = m.group(1), m.group(2)
            if isinstance(current, dict):
                current = current.get(key_name)
            else:
                return None

            if current is None or not isinstance(current, list):
                return None

            if idx_str == "*":
                # 返回整个列表
                continue
            else:
                idx = int(idx_str)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
        else:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return current


def extract_json_field(
    data: Any,
    rule: FieldExtractor,
    base_url: str = "",
) -> str:
    """根据抽取规则从 JSON 节点抽取单个字段字符串。"""
    raw_val = ""

    if rule.type == "constant":
        return rule.default or ""

    if rule.selector:
        val = get_json_path_value(data, rule.selector)
        if val is not None:
            raw_val = str(val)

    if not raw_val and rule.default:
        raw_val = rule.default

    # 二次正则提纯
    if raw_val and rule.regex:
        m = re.search(rule.regex, raw_val)
        if m:
            try:
                raw_val = m.group(rule.regex_group)
            except IndexError:
                raw_val = m.group(0)

    # 模板拼接
    if rule.template and raw_val:
        raw_val = rule.template.format(value=raw_val)

    # 相对 URL 补全
    if base_url and raw_val and (raw_val.startswith("/") or raw_val.startswith("./")):
        raw_val = safe_resolve_url(base_url, raw_val)

    if rule.strip:
        raw_val = collapse_whitespace(raw_val)

    return raw_val
