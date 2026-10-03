"""站点的后台设置：**启用 / 停用**与显示顺序。

源本身有一个真相：``crawler/sites/<key>.py`` 存在即存在（:meth:`SiteRegistry.keys` 扫目录）。
但"这个源现在要不要给用户看"是**另一件事** —— 它是运维的意图，必须满足三条：

* 点了**立刻生效**（用户端的站点列表马上少一项）；
* **重启后还在**（不能只是内存里的一个变量）；
* 事后能对上（什么时候关的、谁关的 —— 审计在路由层记）。

所以它进数据库，与爬虫文件分开：**文件代表"有什么"，这张表代表"给不给看"。**

**没有记录 = 启用。** 于是加一个新源不需要先来这里"注册"，
这条特性上线时也不会改变任何既有行为（包括既有的测试）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base


class SiteSetting(Base):
    __tablename__ = "site_settings"

    #: 站点 key = 爬虫文件名（``crawler/sites/<key>.py``），所以它本身就是主键
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: 停用 = 用户端列表里不出现它，内容接口直接回 ``SITE_DISABLED``（不 fork 爬虫）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    #: 显示顺序（小的在前）。留 10 的间隔是为了将来能手动插进去一个
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    #: 运维备注（"源站改版了先关掉"之类）
    note: Mapped[str] = mapped_column(String(255), default="")

    #: 自定义站点对外显示名（为空则显示源站原始 name）
    custom_name: Mapped[str] = mapped_column(String(128), default="")
    #: 站点标识徽标（如 "4K", "极速", "推荐"）
    badge: Mapped[str] = mapped_column(String(32), default="")
    #: 单站自定义超时秒数（0 或更小表示跟随全局默认配置）
    timeout_seconds: Mapped[float] = mapped_column(default=0.0)

    #: 分类与子分类控制规则 JSON（隐藏、重命名、排序、子分类）
    category_rules_json: Mapped[str] = mapped_column(String(4096), default="{}")
    #: 详情页显示与清洗策略 JSON（广告过滤、线路映射、集数命名、兜底海报）
    detail_policy_json: Mapped[str] = mapped_column(String(4096), default="{}")
    #: 单站独立缓存策略 JSON（home_ttl, category_ttl, detail_ttl）
    cache_policy_json: Mapped[str] = mapped_column(String(2048), default="{}")

    #: 单站独立代理控制开关与地址
    proxy_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    proxy_url: Mapped[str] = mapped_column(String(255), default="")
    proxy_node_id: Mapped[str] = mapped_column(String(64), default="")

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
