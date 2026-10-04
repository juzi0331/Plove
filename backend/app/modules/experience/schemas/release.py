"""体验层发布历史、发布与回滚契约 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExperienceReleaseItem(BaseModel):
    """单条发布历史记录概要。"""

    release_id: str = Field(description="发布唯一 ID")
    revision: int = Field(description="自增修订号")
    published_at: str = Field(description="发布时间")
    published_by: str = Field(description="发布操作者")
    note: str = Field(default="", description="发布说明或回滚来源备注")
    is_active: bool = Field(default=False, description="当前是否为全站激活中版本")


class ReleasePublishRequest(BaseModel):
    """从草稿创建不可变发布快照请求。"""

    draft_id: str = Field(default="default", description="草稿 ID")
    note: str = Field(default="", description="本次发布说明，如 '调整首页横幅与主题红色'")


class ReleasePublishResult(BaseModel):
    """发布结果。"""

    release_id: str = Field(description="新生成的发布版本 ID")
    revision: int = Field(description="新生成的修订号")
    message: str = Field(description="反馈提示信息")


class ReleaseRollbackRequest(BaseModel):
    """回滚至指定历史快照请求。"""

    target_release_id: str | None = Field(default=None, description="要回退到的历史发布快照 ID（默认使用 URL 路径中的 release_id）")
    note: str = Field(default="", description="回滚原因说明")
