"""主题安全规则与 Token 边界校验。

阻止任意 CSS 字符串注入或越界破坏布局的数值下发。
所有数值均受物理极限与安全约束保护。
"""

from __future__ import annotations

import re

_HEX_COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_SAFE_COLOR_KEYWORDS = {"transparent", "currentColor", "inherit"}

# 安全数值边界
BODY_PX_RANGE = (12, 24)
TITLE_PX_RANGE = (18, 48)
MAX_WIDTH_PX_RANGE = (960, 2560)
PADDING_PX_RANGE = (0, 64)
GAP_PX_RANGE = (0, 48)
RADIUS_PX_RANGE = (0, 32)
DURATION_MS_RANGE = (0, 1000)

ALLOWED_FAMILIES = {"system", "inter", "roboto", "outfit", "sans-serif"}
ALLOWED_ASPECT_RATIOS = {"16:9", "2:3", "3:4", "1:1", "4:3"}
ALLOWED_IMAGE_FITS = {"cover", "contain"}
ALLOWED_MOTION_PRESETS = {"none", "subtle", "smooth"}


def is_safe_color(val: str) -> bool:
    """校验色彩是否为安全合法的 Hex 或受控安全关键字，禁止自由拼接任意 CSS。"""
    if not val or not isinstance(val, str):
        return False
    clean = val.strip()
    if clean in _SAFE_COLOR_KEYWORDS:
        return True
    return bool(_HEX_COLOR_PATTERN.match(clean))


def sanitize_color(val: str, fallback: str) -> str:
    """如果色彩不合法则回退到安全默认值。"""
    return val.strip() if is_safe_color(val) else fallback


def validate_theme_tokens(data: dict) -> list[str]:
    """验证主题 Token 字典，返回遇到的所有校验错误提示。"""
    errors: list[str] = []

    # 检查色彩
    color = data.get("color", {})
    if isinstance(color, dict):
        for k, v in color.items():
            if isinstance(v, str) and not is_safe_color(v):
                errors.append(f"色彩字段 '{k}' 值 '{v}' 非合法 Hex 颜色")

    # 检查排版
    typo = data.get("typography", {})
    if isinstance(typo, dict):
        body_px = typo.get("body_px")
        if body_px is not None and not (BODY_PX_RANGE[0] <= body_px <= BODY_PX_RANGE[1]):
            errors.append(f"正文字号 body_px ({body_px}) 超出安全范围 {BODY_PX_RANGE}")
        title_px = typo.get("title_px")
        if title_px is not None and not (TITLE_PX_RANGE[0] <= title_px <= TITLE_PX_RANGE[1]):
            errors.append(f"标题字号 title_px ({title_px}) 超出安全范围 {TITLE_PX_RANGE}")
        fam = typo.get("family")
        if fam and fam not in ALLOWED_FAMILIES:
            errors.append(f"不支持的字体族 '{fam}'，仅允许 {ALLOWED_FAMILIES}")

    # 检查卡片
    card = data.get("card", {})
    if isinstance(card, dict):
        ratio = card.get("aspect_ratio")
        if ratio and ratio not in ALLOWED_ASPECT_RATIOS:
            errors.append(f"不支持的卡片比例 '{ratio}'")
        rad = card.get("radius_px")
        if rad is not None and not (RADIUS_PX_RANGE[0] <= rad <= RADIUS_PX_RANGE[1]):
            errors.append(f"卡片圆角 radius_px ({rad}) 超出安全范围 {RADIUS_PX_RANGE}")

    # 检查动效
    motion = data.get("motion", {})
    if isinstance(motion, dict):
        dur = motion.get("duration_ms")
        if dur is not None and not (DURATION_MS_RANGE[0] <= dur <= DURATION_MS_RANGE[1]):
            errors.append(f"动效持续时间 duration_ms ({dur}) 超出安全范围 {DURATION_MS_RANGE}")

    return errors
