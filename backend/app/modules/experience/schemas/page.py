"""体验层页面定义与 ViewModel Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.experience.schemas.components import SectionDefinition


class PageDefinition(BaseModel):
    """页面结构配置（保存在草稿与发布快照中）。"""

    id: str = Field(description="页面 ID，如 'home_default'、'category_default'")
    title: str = Field(default="首页", description="页面标题")
    sections: list[SectionDefinition] = Field(default_factory=list, description="包含的组件区块清单")


class PageViewModel(BaseModel):
    """面向客户端渲染的页面视图模型。"""

    schema_version: str = Field(default="1.0", description="协议架构版本")
    release_id: str = Field(description="对应的体验发布快照 ID")
    page_id: str = Field(description="页面 ID")
    title: str = Field(description="页面标题")
    content_revision: str = Field(default="1", description="内容数据修订版本")
    sections: list[SectionDefinition] = Field(default_factory=list, description="已绑定真实数据的有序组件区块")
