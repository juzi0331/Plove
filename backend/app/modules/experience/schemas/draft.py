"""体验层草稿编辑与保存 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.experience.schemas.bootstrap import NavigationItem
from app.modules.experience.schemas.page import PageDefinition
from app.modules.experience.schemas.theme import BrandConfig, PlayerDefaults, ThemeConfig


class ExperienceDraftPayload(BaseModel):
    """管理后台读取的当前草稿完整配置。"""

    draft_id: str = Field(default="default", description="草稿 ID")
    revision: int = Field(description="乐观并发锁修订号")
    brand: BrandConfig = Field(default_factory=BrandConfig, description="品牌配置")
    theme: ThemeConfig = Field(default_factory=ThemeConfig, description="主题视觉 Token")
    text: dict[str, str] = Field(default_factory=dict, description="全局文案字典")
    navigation: list[NavigationItem] = Field(default_factory=list, description="前台导航项列表")
    pages: dict[str, PageDefinition] = Field(default_factory=dict, description="受控页面配置映射表 {page_id: PageDefinition}")
    player_defaults: PlayerDefaults = Field(default_factory=PlayerDefaults, description="播放器默认偏好")
    updated_at: str = Field(description="最后保存时间")
    updated_by: str = Field(description="最后修改人")


class ExperienceDraftUpdateRequest(BaseModel):
    """提交修改草稿请求（必须携带 revision 防止多人并发覆盖）。"""

    revision: int = Field(description="基于的当前版本号（乐观并发锁）")
    brand: BrandConfig | None = Field(default=None, description="品牌配置变更")
    theme: ThemeConfig | None = Field(default=None, description="主题视觉变更")
    text: dict[str, str] | None = Field(default=None, description="全局文案字典变更")
    navigation: list[NavigationItem] | None = Field(default=None, description="导航项列表变更")
    pages: dict[str, PageDefinition] | None = Field(default=None, description="页面配置映射变更")
    player_defaults: PlayerDefaults | None = Field(default=None, description="播放器默认偏好变更")


class DraftSaveResult(BaseModel):
    """草稿保存结果。"""

    draft_id: str = Field(description="草稿 ID")
    revision: int = Field(description="保存后的新版本号")
    message: str = Field(description="反馈信息")
