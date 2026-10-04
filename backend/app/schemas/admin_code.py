"""后台激活码管理契约。

包含发码、延长、停用/启用、设备统计、批量清理等请求与回执载荷。
对应契约: admin-code-*.json
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class CodeListItem(BaseModel):
    """后台列表里的一行激活码。"""

    id: int
    code: str
    note: str = ""
    duration_hours: int = Field(description="发码时给的时长（小时）—— **历史记录**，不是当前剩余")
    created_at: datetime
    activated_at: datetime | None = Field(default=None, description="首次激活时间；为空 = 还没被用过")
    expires_at: datetime | None = Field(default=None, description="到期时间；为空 = 还没开始计时")
    disabled_at: datetime | None = Field(default=None, description="停用时间；非空 = 这个码现在用不了")
    remaining_seconds: int = Field(
        default=0,
        description="还剩多少秒。**0 有两种含义**：还没激活（``activated_at`` 为空），"
        "或者已经到期了。界面必须结合 ``activated_at`` 才能说清是哪种",
    )
    device_count: int = Field(default=0, description="这个码用过几台设备")
    max_devices: int = Field(default=1, description="最多允许绑定的设备数（仅后台可见）")
    active_device_name: str | None = Field(default=None, description="当前活跃的那台设备名")
    is_online: bool = Field(default=False, description="当前是否有设备在线")
    is_playing: bool = Field(default=False, description="当前是否正在播放影片")
    current_playback: str | None = Field(default=None, description="当前正在观看的剧名与集数")

    @property
    def is_disabled(self) -> bool:  # pragma: no cover - 方便 Python 侧读
        return self.disabled_at is not None


class CodeListPayload(BaseModel):
    """激活码列表（分页）。"""

    codes: list[CodeListItem] = Field(default_factory=list)
    total: int = Field(default=0, description="**满足搜索条件的总数**，不是本页条数")
    page: int = 1
    page_size: int = 20


class IssueCodesRequest(BaseModel):
    """发码。``hours`` / ``days`` 二选一。"""

    hours: int | None = Field(default=None, ge=1, le=24 * 365)
    days: int | None = Field(default=None, ge=1, le=365)
    count: int = Field(default=1, ge=1, le=50, description="一次发几个（上限 50，防止手滑发出 5000 个）")
    max_devices: int = Field(default=1, ge=1, le=100, description="最多允许几台设备使用该码（对用户端严格保密）")
    note: str = Field(default="", max_length=255, description="备注：发给谁 / 哪一批")

    @model_validator(mode="after")
    def _exactly_one_duration(self) -> IssueCodesRequest:
        if (self.hours is None) == (self.days is None):
            raise ValueError("hours 与 days 必须给一个、且只能给一个")
        return self

    @property
    def total_hours(self) -> int:
        return self.hours if self.hours is not None else (self.days or 0) * 24


class IssueCodesResult(BaseModel):
    """发码的回执。**码本身一定要回给调用方** —— 它是唯一的交付物。"""

    codes: list[str] = Field(default_factory=list)
    duration_hours: int
    note: str = ""


class ExtendRequest(BaseModel):
    """延长时长。**只能加时间，不能减** —— 减时间应该用停用。"""

    hours: int = Field(ge=1, le=24 * 365)


class CodeActionResult(BaseModel):
    """停用 / 启用 / 延长之后的回执：说明 + 变更后的那一行。

    回带整行而不是只回一个 ``ok``：界面可以直接用它刷新那一行，
    不用再多发一次列表请求（也就不会出现"操作成功了但列表还是旧值"）。
    """

    message: str
    code: CodeListItem


class CodeCleanupResult(BaseModel):
    """批量清理失效激活码结果。"""

    deleted_count: int = Field(description="删除的失效激活码数量")
    message: str = Field(description="提示信息")
