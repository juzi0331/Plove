"""页面结构与组件布局安全规则。"""

from __future__ import annotations

import re
from typing import Any

from app.modules.experience.domain.component_registry import is_component_supported

MAX_SECTIONS_PER_PAGE = 50
MAX_ITEMS_PER_SECTION = 100
_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def validate_section(section: dict[str, Any]) -> list[str]:
    """校验单个 Section 定义是否合规。"""
    errors: list[str] = []
    sec_id = section.get("id", "")
    if not _SAFE_ID_PATTERN.match(str(sec_id)):
        errors.append(f"Section ID '{sec_id}' 不符合安全命名规范 (1-64 位字母数字中划线或下划线)")

    comp = section.get("component", "")
    if not is_component_supported(comp):
        errors.append(f"未支持的未知组件: '{comp}'")

    props = section.get("props")
    if not isinstance(props, dict):
        errors.append(f"Section '{sec_id}' 的 props 必须是字典对象")

    return errors


def validate_page_sections(sections: list[dict[str, Any]]) -> list[str]:
    """校验页面包含的全部 Sections。"""
    if len(sections) > MAX_SECTIONS_PER_PAGE:
        return [f"页面组件数量 ({len(sections)}) 超出单页上限 {MAX_SECTIONS_PER_PAGE}"]

    errors: list[str] = []
    seen_ids: set[str] = set()
    for sec in sections:
        if not isinstance(sec, dict):
            errors.append("Section 节点必须是有效对象")
            continue
        sec_id = sec.get("id", "")
        if sec_id in seen_ids:
            errors.append(f"重复的 Section ID: '{sec_id}'")
        seen_ids.add(sec_id)
        errors.extend(validate_section(sec))

    return errors
