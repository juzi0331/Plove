"""时间。

只有一条规矩，但必须**全项目统一**，否则一定出时区 bug：

* **存进数据库的一律是 naive UTC**（MySQL 的 DATETIME 不带时区，存 aware 会丢信息）；
* **出给前端的永远是 aware UTC**（序列化成带 ``Z`` / ``+00:00`` 的字符串，
  客户端才知道那是 UTC）。

所以边界只有两个：写库前用 :func:`utcnow`，出接口前用 :func:`as_aware`。
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """当前时间，naive UTC。**所有写库的地方都用它**。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_aware(value: datetime | None) -> datetime | None:
    """把从库里读出来的 naive UTC 变成 aware UTC。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
