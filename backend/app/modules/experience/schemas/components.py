"""体验层交互动作与组件属性规范。"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ActionPayload(BaseModel):
    """命名意图动作描述。由前端映射至受控处理函数，不执行动态代码。"""

    type: str = Field(description="动作类型: open_home, open_category, open_detail, start_playback, select_episode, request_source_switch, redeem, acknowledge_notice")
    content_id: str | None = Field(default=None, description="影片或条目规范标识")
    category_id: str | None = Field(default=None, description="分类标识")
    site_key: str | None = Field(default=None, description="源站标识")
    episode_id: str | None = Field(default=None, description="剧集标识")
    notice_id: str | None = Field(default=None, description="公告标识")
    url: str | None = Field(default=None, description="安全目标路径")


class SectionBadge(BaseModel):
    """卡片或区块角标。"""

    text: str = Field(description="角标文本，如 '新上线'、'热播'")
    tone: str = Field(default="primary", description="色调风格: primary / muted / warning")


class SectionItem(BaseModel):
    """视频栏目或网格单个展示项。"""

    content_id: str = Field(description="规范内容 ID")
    title: str = Field(description="影片主标题")
    subtitle: str = Field(default="", description="副标题或更新集数")
    poster_url: str = Field(default="", description="海报图片链接（经由受控图片出口解析）")
    fallback_asset_id: str = Field(default="poster_default", description="图片加载失败时的后备内置占位图")
    badge: SectionBadge | None = Field(default=None, description="可选角标")
    action: ActionPayload | None = Field(default=None, description="点击交互动作")


class SectionDefinition(BaseModel):
    """页面中单个组件区块。"""

    id: str = Field(description="区块唯一 ID，如 'hero_main'、'hot_rail'")
    component: str = Field(description="组件名: hero / video_rail / video_grid / notice / empty_state")
    component_version: int = Field(default=1, description="组件协议版本号")
    style: dict[str, Any] = Field(default_factory=dict, description="受控呈现样式参数 (如 card_variant, density)")
    props: dict[str, Any] = Field(default_factory=dict, description="传递给组件的数据属性")
