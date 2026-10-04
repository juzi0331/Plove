"""播放地址与前台播放心跳与进度上报载荷。"""

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


class PlaybackHeartbeatRequest(BaseModel):
    vod_id: str = Field(description="影视剧 ID")
    vod_name: str = Field(default="", description="影视剧名称")
    vod_pic: str = Field(default="", description="海报封面地址")
    ep_name: str = Field(default="", description="当前集数名称")
    site: str = Field(default="", description="当前来源站点 key")
    position: float = Field(default=0.0, description="当前播放时间秒数")
    duration: float = Field(default=0.0, description="总时长秒数")
    progress: int = Field(default=0, ge=0, le=100, description="播放进度百分比 0-100")
    is_playing: bool = Field(default=True, description="当前是否处于播放中状态")


class PlaybackHeartbeatResult(BaseModel):
    ok: bool = True
    message: str = "ok"
