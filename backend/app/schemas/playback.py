"""播放地址。

**绝不入库**：m3u8 普遍带时效签名（2048ai 的 ``auth_key``、ncat21 的 ``timestamp``），
数据库只存可复现的定位符 ``site_id + vod_id + ep_index(+ line)``，每次播放现取。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Playback(BaseModel):
    """一次调用的播放结果。"""

    url: str
    format: Literal["m3u8", "mp4"] = "m3u8"
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="防盗链用的 Referer / User-Agent；直连和代理都要带上",
    )
