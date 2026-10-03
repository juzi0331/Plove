"""源开关与显示顺序：**数据库是真相，进程内是快照。**

### 为什么要有快照

两个读者，都拿不到 Session：

1. :class:`app.crawler.registry.SiteRegistry` —— 进程内单例，内容接口与**预热线程**
   都要问它"这个源现在许不许调用"。它不可能为每次判断开一个数据库会话；
2. 用户端的 ``GET /sites`` —— 每次请求虽然手里有 Session，但也没必要为了一条
   极小概率变化的数据每次查库。

所以状态放一份**进程内快照**，刷新时机就两个：

* **内容请求**（``require_device`` 里）带 5 秒 TTL 顺手刷一下 —— 它守在所有内容接口上，
  手里已经有 Session，是唯一"不会漏掉新增路由"的位置；
* **后台的写操作**强制刷新 —— 保证"点了就生效"，而不是等 5 秒。

### 默认全开

没有记录 = 启用。所以"这条特性上线"和"加一个新源"都不需要额外的登记动作，
也不会改变任何既有行为。

### 为什么停用要拦在注册表里

注册表是**唯一通往爬虫的关口**（见它的模块说明）。把关口设在这里的收益很具体：
用户端、后台预览、预热、将来任何新的调用路径，都会自动被这一条拦住 ——
把关口设在某个 service 上，早晚会漏掉一条新加的路径。

**不 import fastapi**（services 层的硬规矩），也不 commit —— 事务归 ``get_db``。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.site_setting import SiteSetting

logger = get_logger(__name__)

#: 快照的存活时间（秒）。单机、用户 < 30、只有后台能改它 —— 5 秒足够快也足够省。
DEFAULT_TTL = 5.0

#: 排顺序时的间隔，留出手动插入的余地（10, 20, 30 …）
ORDER_STEP = 10


@dataclass(frozen=True, slots=True)
class SiteConfig:
    """一条源设置。"""

    key: str
    enabled: bool = True
    sort_order: int = 0
    note: str = ""
    custom_name: str = ""
    badge: str = ""
    timeout_seconds: float = 0.0
    category_rules_json: str = "{}"
    detail_policy_json: str = "{}"
    cache_policy_json: str = "{}"
    proxy_enabled: bool = False
    proxy_url: str = ""


class SiteSettingsStore:
    """进程内快照。线程安全（写操作来自请求线程，读来自请求线程与预热线程）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, SiteConfig] = {}
        self._loaded = False
        self._loaded_at = 0.0

    # ------------------------------------------------------------------ 刷新

    def refresh(self, session: Session, *, force: bool = False, ttl: float = DEFAULT_TTL) -> None:
        """按 TTL 重新读一遍库。``force=True`` 用于后台的写操作之后。"""
        now = time.monotonic()
        with self._lock:
            if not force and self._loaded and now - self._loaded_at < ttl:
                return

        rows = session.scalars(select(SiteSetting)).all()
        items = {
            row.key: SiteConfig(
                key=row.key,
                enabled=bool(row.enabled),
                sort_order=int(row.sort_order or 0),
                note=row.note or "",
                custom_name=getattr(row, "custom_name", "") or "",
                badge=getattr(row, "badge", "") or "",
                timeout_seconds=float(getattr(row, "timeout_seconds", 0.0) or 0.0),
                category_rules_json=getattr(row, "category_rules_json", "{}") or "{}",
                detail_policy_json=getattr(row, "detail_policy_json", "{}") or "{}",
                cache_policy_json=getattr(row, "cache_policy_json", "{}") or "{}",
                proxy_enabled=bool(getattr(row, "proxy_enabled", False)),
                proxy_url=getattr(row, "proxy_url", "") or "",
            )
            for row in rows
        }
        with self._lock:
            self._items = items
            self._loaded = True
            self._loaded_at = time.monotonic()

    def forget(self) -> None:
        """清空快照（测试之间隔离、或换过库时用）。"""
        with self._lock:
            self._items = {}
            self._loaded = False
            self._loaded_at = 0.0

    # ------------------------------------------------------------------ 读

    def config(self, key: str) -> SiteConfig:
        with self._lock:
            found = self._items.get(key)
        return found if found is not None else SiteConfig(key=key)

    def is_enabled(self, key: str) -> bool:
        return self.config(key).enabled

    def disabled_keys(self) -> frozenset[str]:
        with self._lock:
            return frozenset(key for key, item in self._items.items() if not item.enabled)

    def order_key(self, key: str) -> tuple[int, str]:
        """排序用的键：先看 ``sort_order``，再按 key —— 顺序必须**稳定**，
        否则每次刷新用户端的站点顺序会自己抖。"""
        config = self.config(key)
        return (config.sort_order, key)

    def sort_keys(self, keys: list[str]) -> list[str]:
        return sorted(keys, key=self.order_key)


# ------------------------------------------------------------------ 进程内单例

_STORE = SiteSettingsStore()


def store() -> SiteSettingsStore:
    return _STORE


def disabled_keys() -> frozenset[str]:
    """给 :class:`SiteRegistry` 用的回调（它只需要知道"哪些不许用"）。

    返回空集合 = 全部可用 —— 这正是"没有记录 = 启用"的直接体现。
    """
    return _STORE.disabled_keys()


def reset_store() -> None:
    _STORE.forget()


# ------------------------------------------------------------------ 数据库读写


def load_all(session: Session) -> dict[str, SiteConfig]:
    session.expire_all()
    rows = session.scalars(select(SiteSetting)).all()
    return {row.key: _to_config(row) for row in rows}


def get_or_create(session: Session, key: str) -> SiteSetting:
    record = session.get(SiteSetting, key)
    if record is None:
        record = SiteSetting(key=key, enabled=True, sort_order=0)
        session.add(record)
        session.flush()
    return record


def set_enabled(session: Session, key: str, *, enabled: bool) -> SiteConfig:
    """启用 / 停用。**第一次写就顺手把记录建出来了** —— 建完默认是启用的。"""
    record = get_or_create(session, key)
    record.enabled = enabled
    session.flush()
    return _to_config(record)


def set_order(session: Session, keys: list[str], *, known: set[str]) -> None:
    """按给定的顺序重排。

    * **未知的 key 直接拒**（``BAD_REQUEST``）：多半是拼错了，静默忽略会让人
      以为"设过了"，然后在用户端看到没变化；
    * **没提到的 key 排在后面**（保持它们之间的相对顺序）：比报错宽容，
      而且"没提到"通常就是"这期间新加了一个源"。
    """
    unknown = [key for key in keys if key not in known]
    if unknown:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"不认识的源：{', '.join(unknown)}（先刷新一下列表）",
        )

    ordered = list(dict.fromkeys(keys))  # 去重但保住顺序
    rest = [key for key in sorted(known) if key not in ordered]

    for index, key in enumerate(ordered + rest, start=1):
        get_or_create(session, key).sort_order = index * ORDER_STEP
    session.flush()


def note(session: Session, key: str, text: str) -> SiteConfig:
    record = get_or_create(session, key)
    record.note = text[:255]
    session.flush()
    return _to_config(record)


def update_advanced(
    session: Session,
    key: str,
    *,
    custom_name: str | None = None,
    badge: str | None = None,
    timeout_seconds: float | None = None,
    note: str | None = None,
    proxy_enabled: bool | None = None,
    proxy_url: str | None = None,
) -> SiteConfig:
    """更新单站高级配置。"""
    record = get_or_create(session, key)
    if custom_name is not None:
        record.custom_name = custom_name.strip()[:128]
    if badge is not None:
        record.badge = badge.strip()[:32]
    if timeout_seconds is not None:
        record.timeout_seconds = max(0.0, float(timeout_seconds))
    if note is not None:
        record.note = note.strip()[:255]
    if proxy_enabled is not None:
        record.proxy_enabled = bool(proxy_enabled)
    if proxy_url is not None:
        record.proxy_url = proxy_url.strip()[:255]
    session.flush()
    return _to_config(record)


def update_category_rules(session: Session, key: str, rules_json: str) -> SiteConfig:
    """更新站点的分类控制规则 JSON。"""
    record = get_or_create(session, key)
    record.category_rules_json = rules_json
    session.flush()
    return _to_config(record)


def update_detail_policy(session: Session, key: str, policy_json: str) -> SiteConfig:
    """更新站点的详情页展示与清洗策略 JSON。"""
    record = get_or_create(session, key)
    record.detail_policy_json = policy_json
    session.flush()
    return _to_config(record)


def _to_config(record: SiteSetting) -> SiteConfig:
    return SiteConfig(
        key=record.key,
        enabled=bool(record.enabled),
        sort_order=int(record.sort_order or 0),
        note=record.note or "",
        custom_name=getattr(record, "custom_name", "") or "",
        badge=getattr(record, "badge", "") or "",
        timeout_seconds=float(getattr(record, "timeout_seconds", 0.0) or 0.0),
        category_rules_json=getattr(record, "category_rules_json", "{}") or "{}",
        detail_policy_json=getattr(record, "detail_policy_json", "{}") or "{}",
        cache_policy_json=getattr(record, "cache_policy_json", "{}") or "{}",
        proxy_enabled=bool(getattr(record, "proxy_enabled", False)),
        proxy_url=getattr(record, "proxy_url", "") or "",
    )
