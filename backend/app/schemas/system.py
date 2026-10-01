"""系统类接口的载荷。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthPayload(BaseModel):
    """健康检查。故意只回最少的字段：它要能在数据库、爬虫全挂时照样返回。"""

    status: Literal["ok"] = "ok"
    env: str
    version: str
