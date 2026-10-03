"""站点元信息 —— 爬虫 ``meta`` 命令的输出。

后端据此**路由**：某个站点没声明 ``search``，网关就该明确回"该源不支持搜索"，
而不是把空列表伪装成"没搜到"。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: 站点 key 就是爬虫的文件名（``sites/<key>.py``）
SITE_KEY_PATTERN = r"^[a-z_][a-z0-9_]*$"


class SiteMeta(BaseModel):
    key: str = Field(min_length=2, max_length=64, pattern=SITE_KEY_PATTERN)
    name: str
    version: str = ""
    base_url: str = ""

    mode: Literal["direct", "proxy"] = Field(
        default="direct",
        description="direct = 前端直连源站；proxy = 必须走后端流代理（防盗链/被墙）",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="支持的命令名，如 home / category / search / detail / play",
    )
    play_format: list[str] = Field(default_factory=list)
    note: str | None = None
    badge: str = Field(default="", description="前台站点角标（如 4K, 极速）")
    custom_name: str = Field(default="", description="前台自定义别名")


class SiteListPayload(BaseModel):
    """站点清单。只有 meta 能拿到（即爬虫文件真的能跑起来）的源才会出现在这里。"""

    sites: list[SiteMeta] = Field(default_factory=list)
