"""系统级配置持久化：全站公告、紧急维护模式、图片代理策略等。

采用 Key-Value JSON 设计，既保证新增系统级设置无需改表，
又保证在 MySQL / SQLite 中均原生兼容。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(String(4096), default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
