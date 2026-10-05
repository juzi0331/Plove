"""播放记录模型。

记录每个设备在各影视剧的播放进度与观看历史。
单设备对单影片唯一（多次观看同一影片时更新集数、进度与时间）。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.activation import ActivationCode
    from app.models.device import Device


class PlaybackRecord(Base):
    __tablename__ = "playback_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    activation_id: Mapped[int] = mapped_column(
        ForeignKey("activation_codes.id", ondelete="CASCADE"), index=True
    )

    vod_id: Mapped[str] = mapped_column(String(64), index=True)
    vod_name: Mapped[str] = mapped_column(String(255), default="")
    vod_pic: Mapped[str] = mapped_column(String(512), default="")
    ep_name: Mapped[str] = mapped_column(String(120), default="")
    site_key: Mapped[str] = mapped_column(String(64), default="")

    position: Mapped[float] = mapped_column(Float, default=0.0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_playing: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    device: Mapped["Device"] = relationship(back_populates="playback_records")
    activation: Mapped["ActivationCode"] = relationship(back_populates="playback_records")

    __table_args__ = (
        UniqueConstraint("device_id", "site_key", "vod_id", name="uq_device_site_vod"),
    )
