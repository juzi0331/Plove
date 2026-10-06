"""客户端启动配置 (Bootstrap) 与版本心跳 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.experience.schemas.components import ActionPayload
from app.modules.experience.schemas.theme import BrandConfig, PlayerDefaults, ThemeConfig


class NavigationItem(BaseModel):
    """前台导航条目。"""

    id: str = Field(description="导航项 ID，如 'home', 'category'")
    label_key: str = Field(description="多语言或文案配置键")
    label: str = Field(description="默认显示文案")
    action: ActionPayload = Field(description="点击跳转意图")


class ClientBootstrapPayload(BaseModel):
    """客户端启动并展示所需的完整基础配置。匿名或已激活客户端均可获取。"""

    schema_version: str = Field(default="1.0", description="Schema 规范版本")
    release_id: str = Field(description="当前生效的发布版本 ID")
    revision: int = Field(description="单调自增的配置修订版本号")
    min_runtime_version: str = Field(default="1.0.0", description="要求的客户端最低运行时版本")
    refresh_after_seconds: int = Field(default=120, description="活跃客户端条件版本查询间隔秒数")
    offline_display_ttl_seconds: int = Field(default=86400, description="离线安全展示有效秒数")
    brand: BrandConfig = Field(default_factory=BrandConfig, description="品牌标识")
    theme: ThemeConfig = Field(default_factory=ThemeConfig, description="主题视觉 Token")
    text: dict[str, str] = Field(default_factory=dict, description="可配置的全局文案映射表")
    navigation: list[NavigationItem] = Field(default_factory=list, description="前台主导航配置")
    page_references: dict[str, str] = Field(
        default_factory=lambda: {"home": "home_default"},
        description="命名路由到页面配置的映射关系",
    )
    player_defaults: PlayerDefaults = Field(default_factory=PlayerDefaults, description="播放器全局呈现参数")


class ReleaseCurrentPayload(BaseModel):
    """客户端快速心跳轻量版本检测载荷。配合 ETag/304 节省流量。"""

    release_id: str = Field(description="当前发布快照 ID")
    revision: int = Field(description="当前生效的修订号")
    published_at: str = Field(description="发布时间 ISO 8601")
