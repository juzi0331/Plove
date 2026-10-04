"""数据库会话与事务提交依赖。"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.services import site_settings


def get_db() -> Iterator[Session]:
    """每个请求一个会话：成功才 commit，出异常回滚。

    注意不要在 service 里 commit —— 一次请求就是一个事务边界，
    事务归这里管，业务层只管改对象。

    但它不够：这里的 commit 跑在依赖清理阶段，也就是响应送出之后
    （这是框架的清理时机，不是我们能选的）。所以任何"客户端拿到 200 就会马上去读"
    的写接口，都要额外调一次 :func:`commit_now`。
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def commit_now(db: Session) -> None:
    """写操作显式提交，让 200 真正意味着"已经落地"。

    为什么不能只依赖 :func:`get_db` 的自动提交：那跑在响应送出之后，
    于是"客户端拿到 200 → 立刻发下一个请求"这条最自然的时序里，
    第二个请求有可能还读不到第一个请求的写。

    所以：写接口的承诺是"客户端读到 200 时，变更已经落库"。
    """
    db.commit()


def get_site_settings(db: Session = Depends(get_db)) -> site_settings.SiteSettingsStore:
    """源开关的进程内快照（按 TTL 刷新）。

    后台的写操作会再显式 refresh(force=True) 一次 ——
    "点了就生效"不能等 TTL，否则运维会以为没点上而再点一次。
    """
    store = site_settings.store()
    store.refresh(db)
    return store
