"""激活码。

规则（已和你确认）：

* **时长制**，凭码管理已激活用户，不做注册；
* **从首次激活那一刻开始算时长**（``activated_at``），换设备不重置、不重算；
* **一码多设备，但同时只能一台在线** —— 那个"同时"就是 ``active_device_id``。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.device import Device


class ActivationCode(Base):
    __tablename__ = "activation_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    #: 这个码给多长的时长（小时）。天数换算在发码时做，库里只存小时，避免单位歧义。
    duration_hours: Mapped[int] = mapped_column(Integer, default=24)
    #: 最多允许绑定的设备数（None 表示不限，数值表示上限，不对普通用户公开）
    max_devices: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    #: 备注：发给谁、哪一批。纯给人看的。
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    #: 首次激活时间。为空 = 这码还没被用过；一旦写上就**不再改**，它就是计时的起点。
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: ``activated_at + duration_hours``。首次激活时算一次存下来，之后只读。
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: 停用时间。写上之后这码彻底不能用（包括换设备、抢活跃位）。
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    #: 当前活跃设备 id。
    #:
    #: **刻意不建外键。** ``devices`` 反过来要引用 ``activation_codes``，
    #: 两个方向互相外键会形成环，SQLite 建表时很难受。
    #: 写入方只有 ``activation_service`` 一处，由它保证一致。
    #: 用单列赋值的好处是切换活跃设备**没有中间态** —— 不存在"两台都算活跃"的瞬间。
    active_device_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    devices: Mapped[list["Device"]] = relationship(
        back_populates="activation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
