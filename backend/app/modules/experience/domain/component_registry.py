"""已受支持的组件注册表与动作规范。

客户端为固定渲染器，仅接受已注册组件；禁止远程注入任意 Vue 模板或脚本代码。
"""

from __future__ import annotations

#: 服务端与客户端共同支持的安全组件列表
SUPPORTED_COMPONENTS: frozenset[str] = frozenset({
    "hero",
    "video_rail",
    "video_grid",
    "notice",
    "empty_state",
    "navigation",
})

#: 允许的命名意图动作（客户端通过固定字典执行，不执行远程函数或脚本）
SUPPORTED_ACTIONS: frozenset[str] = frozenset({
    "open_home",
    "open_category",
    "open_detail",
    "start_playback",
    "select_episode",
    "request_source_switch",
    "redeem",
    "acknowledge_notice",
})


def is_component_supported(component_name: str) -> bool:
    return component_name in SUPPORTED_COMPONENTS


def is_action_supported(action_type: str) -> bool:
    return action_type in SUPPORTED_ACTIONS
