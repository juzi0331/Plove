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


class DeviceListPayload(BaseModel):
    """某个码用过的所有设备。"""

    devices: list[DeviceItem] = Field(default_factory=list)
    active_device_id: int | None = None


class KickResult(BaseModel):
    """踢设备的回执。"""

    message: str
    code: CodeListItem
