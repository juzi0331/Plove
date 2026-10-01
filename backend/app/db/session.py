"""引擎与会话。

引擎做成**进程内单例**：每次请求新建引擎会把连接池也一起新建，
那是把连接池的意义完全抹掉。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _options_for(url: str, echo: bool) -> dict:
    options: dict = {"echo": echo, "future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        # SQLite 默认不让跨线程用同一连接，FastAPI 会把同步路由丢进线程池
        options["connect_args"] = {"check_same_thread": False}
        # 内存库必须共用同一个连接，否则每个连接看到的是各自的空库
        if ":memory:" in url:
            options["poolclass"] = StaticPool
    return options


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        _engine = create_engine(url, **_options_for(url, settings.database_echo))
        _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
        try:
            from app.db.schema import create_schema

            create_schema(_engine)
        except Exception as exc:
            import logging

            logging.getLogger("db").warning("数据库 schema 对齐异常: %s", exc)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """给脚本/工具用的会话：自动 commit / rollback / close。

    接口里**不要**用它，那里用 ``app/api/deps.py`` 的 ``get_db`` 依赖。
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


def dispose_engine() -> None:
    """丢掉引擎缓存。测试与切换配置时用。"""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def commit_now(session: Session) -> None:
    """显式提交会话变更。"""
    session.commit()

