"""影片卡片与分类 —— 全站统一字段。

前端只写**一套**卡片 UI，所以字段名必须和爬虫的输出逐字对齐，
源站的私有字段一律在爬虫层归一化，不许泄漏到 UI。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubCategory(BaseModel):
    """子分类或过滤标签。"""

    tid: str = Field(description="子分类 id")
    name: str = ""
    custom_name: str = ""
    hidden: bool = False


class VodCategory(BaseModel):
    """站级动态分类，由爬虫的 ``home`` 返回，前端不写死。"""

    tid: str = Field(description="站内分类 id，原样透传")
    name: str = ""
    custom_name: str = ""
    hidden: bool = False
    subcategories: list[SubCategory] = Field(default_factory=list, description="该分类下的子分类列表")


class VodItem(BaseModel):
    """统一的影片卡片。

    必填四项是硬约定（见 crawler-plan.md 2.4）——缺了就该在爬虫那侧被丢掉，
    不允许"凑合入库"。

    源站可能带扩展字段，一律忽略而不是报错：扩展字段是给上游自己玩的，
    不进契约。
    """

    vod_id: str = Field(description="站内唯一且可复现；多线路时用完整路径，不要抠数字")
    vod_name: str
    vod_pic: str
    vod_remarks: str

    vod_year: int | None = None
    vod_area: str | None = None
    vod_type: str | None = None
    vod_actor: str | None = None
    vod_score: float | None = None
