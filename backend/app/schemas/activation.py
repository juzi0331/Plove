"""激活与会话的接口形状。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RedeemRequest(BaseModel):
    """激活请求。两种用法：

    * **首次激活**：只给 ``code``；
    * **被踢后抢回**（"在此设备继续"）：给 ``device_token``，``code`` 可省。

    为什么把这两件事合成一个动作？因为它们本质是同一件事：
    **"把活跃位指到这台上"**。分开做会多一套状态和一堆边界情况。
    """

    code: str | None = Field(default=None, min_length=1, max_length=64)
    device_token: str | None = Field(default=None, max_length=128)
    device_name: str = Field(default="", max_length=120, description="客户端自报的展示名，仅用于后台查看")


class ActivationResult(BaseModel):
    """激活成功后的状态。"""

    device_token: str
    device_name: str
    expires_at: datetime = Field(description="到期时间，带时区的 UTC")
    remaining_seconds: int = Field(description="还剩多少秒。客户端主要用它，少碰时间戳")
    heartbeat_interval_seconds: int


class SessionState(BaseModel):
    """心跳返回的会话状态。

    ``is_active`` 是**单会话模型的抓手**：为 false 就说明活跃位已经被别的设备拿走了，
    客户端应当立即停止播放并提示用户，而不是自己抢回来。
    """

    is_active: bool
    expires_at: datetime
    remaining_seconds: int
    server_time: datetime
    heartbeat_interval_seconds: int
