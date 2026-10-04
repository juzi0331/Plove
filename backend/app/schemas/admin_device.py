"""后台设备管理契约。

包含激活码设备绑定列表、状态标识与踢设备回执载荷。
注意：设备令牌（Device.token）永远不以明文出现在任何载荷里，仅提供 token_prefix 前缀。
对应契约: admin-device-*.json
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.admin_code import CodeListItem


class DeviceItem(BaseModel):
    """一台设备。**没有 token 字段，只有掩码前缀**（见文件头）。"""

    id: int
    name: str = ""
    token_prefix: str = Field(description="令牌前 6 位，只为让后台能区分是哪一台")
    created_at: datetime
    last_seen_at: datetime = Field(description="最后一次心跳/请求时间")
    is_active: bool = Field(description="它是不是当前占着活跃位的那台")
    is_playing: bool = Field(default=False, description="当前是否正在播放影片")
    current_vod_title: str = Field(default="", description="当前正在观看的剧名与集数")
    last_playback_at: datetime | None = Field(default=None, description="最后播放上报时间")


class DeviceListPayload(BaseModel):
    """某个码用过的所有设备。"""

    devices: list[DeviceItem] = Field(default_factory=list)
    active_device_id: int | None = None


class KickResult(BaseModel):
    """踢设备的回执。"""

    message: str
    code: CodeListItem


class DevicePlaybackHistoryItem(BaseModel):
    """单条播放足迹记录。"""

    id: int
    vod_id: str
    vod_name: str
    vod_pic: str = ""
    ep_name: str = ""
    site_key: str = ""
    position: float = 0.0
    duration: float = 0.0
    progress_percent: int = 0
    is_playing: bool = False
    updated_at: datetime


class DevicePlaybackHistoryPayload(BaseModel):
    """设备观看记录载荷。"""

    device_id: int
    device_name: str = ""
    records: list[DevicePlaybackHistoryItem] = Field(default_factory=list)
    total: int = 0

