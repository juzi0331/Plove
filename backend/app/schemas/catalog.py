"""目录接口的三种载荷：首页 / 列表 / 详情。

列表用的是**同一套结构**（``category`` 与 ``search`` 复用），前端因此只需要一个列表组件。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.episode import Episode, LineInfo
from app.schemas.vod import VodCategory, VodItem


class HomeSection(BaseModel):
    """首页板块。源站自己的分组结构，前端可选使用。"""

    title: str
    videos: list[VodItem] = Field(default_factory=list)


class HomePayload(BaseModel):
    categories: list[VodCategory] = Field(default_factory=list)
    recommend: list[VodItem] = Field(default_factory=list)
    sections: list[HomeSection] = Field(default_factory=list)


class ListPayload(BaseModel):
    """分类与搜索共用。"""

    videos: list[VodItem] = Field(default_factory=list)
    page: int = 1
    has_more: bool = False


class DetailPayload(BaseModel):
    video: VodItem
    desc: str = ""
    episodes: list[Episode] = Field(default_factory=list)
    lines: list[LineInfo] = Field(default_factory=list)
