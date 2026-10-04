"""体验层 ORM 模型：草稿、不可变发布快照与当前激活指针。

遵循蓝图架构：
- 权威存储由数据库承载，带有显式 revision 与乐观并发控制
- 发布为不可变快照 (ExperienceRelease)，支持回滚（生成更高 revision 的新发布）
- 指针 (ExperienceActivePointer) 原子切换
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base


class ExperienceDraft(Base):
    """前台体验（主题、品牌、导航、页面）编辑草稿。"""

    __tablename__ = "experience_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    brand_json: Mapped[str] = mapped_column(Text, default="{}")
    theme_json: Mapped[str] = mapped_column(Text, default="{}")
    navigation_json: Mapped[str] = mapped_column(Text, default="[]")
    pages_json: Mapped[str] = mapped_column(Text, default="{}")
    player_defaults_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str] = mapped_column(String(128), default="admin")


class ExperienceRelease(Base):
    """不可变的前台体验发布快照。"""

    __tablename__ = "experience_releases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    brand_json: Mapped[str] = mapped_column(Text, default="{}")
    theme_json: Mapped[str] = mapped_column(Text, default="{}")
    navigation_json: Mapped[str] = mapped_column(Text, default="[]")
    pages_json: Mapped[str] = mapped_column(Text, default="{}")
    player_defaults_json: Mapped[str] = mapped_column(Text, default="{}")
    published_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    published_by: Mapped[str] = mapped_column(String(128), default="admin")
    note: Mapped[str] = mapped_column(String(256), default="")


class ExperienceActivePointer(Base):
    """各渠道或平台当前生效的发布指针。"""

    __tablename__ = "experience_active_pointers"

    channel: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    release_id: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
