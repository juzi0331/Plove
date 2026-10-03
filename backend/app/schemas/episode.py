"""剧集与播放线路。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LineInfo(BaseModel):
    """一条播放线路。多线路源必须让上层知道有几条线、各有多少集。"""

    line: int = Field(description="线路号，1 起算")
    name: str = ""
    count: int = 0


class Episode(BaseModel):
    """单集。

    ``ep_index`` 是 **1 起算的集号**，不是数组下标。

    ``play_id`` 的含义由爬虫定义：后端拿到它去调 ``play``，自行不作解释。
    多线路源的集号会重复，必须靠 ``line`` 区分——所以 ``play_id`` 建议用完整路径
    （见 crawler-plan.md 的"最容易踩的坑"）。
    """

    ep_index: int = Field(ge=1, description="1 起算的集号")
    ep_name: str = ""
    play_id: str

    line: int | None = Field(default=None, description="多线路源才有；单线路为 null")
    duration_sec: int | None = None
