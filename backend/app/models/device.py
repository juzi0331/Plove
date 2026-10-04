"""设备。

关键：**设备身份由后端签发**（``token``），不接受客户端自报的 device_id。
客户端能改的东西都不算数 —— 那种"设备指纹"两行代码就能伪造。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.activation import ActivationCode
    from app.models.playback import PlaybackRecord


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activation_id: Mapped[int] = mapped_column(
        ForeignKey("activation_codes.id", ondelete="CASCADE"), index=True
    )

    #: 后端签发的设备令牌（``secrets.token_urlsafe``）。客户端保存它，之后每次请求带上。
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: 客户端自报的展示名（"iPhone 15" 之类）。**仅用于后台看一眼，不参与任何判断。**
    name: Mapped[str] = mapped_column(String(120), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    #: 最后一次心跳/激活时间。后台用它判断"这台还在不在线"。
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    #: 当前是否正在播放影片
    is_playing: Mapped[bool] = mapped_column(Boolean, default=False)
    #: 当前正在播放的影片标题与集数
    current_vod_title: Mapped[str] = mapped_column(String(255), default="")
    #: 最后一次播放上报时间
    last_playback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    activation: Mapped["ActivationCode"] = relationship(back_populates="devices")
    playback_records: Mapped[list["PlaybackRecord"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
