"""建表与连接串处理。"""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

import app.models  # noqa: F401 - 必须导入，否则 Base.metadata 里没有表
from app.db.base import Base


def create_schema(engine: Engine) -> list[str]:
    """建表（已存在的跳过），并自动补充已有表缺失的列。返回表名。"""
    Base.metadata.create_all(engine)
    _align_columns(engine)
    return table_names(engine)


def _align_columns(engine: Engine) -> None:
    """自动给已有表补充模型新声明的字段（轻量无侵入的 auto-migration）。"""
    from sqlalchemy import text

    insp = inspect(engine)
    if "site_settings" in insp.get_table_names():
        existing_cols = {c["name"] for c in insp.get_columns("site_settings")}
        needed = {
            "custom_name": "VARCHAR(128) DEFAULT ''",
            "badge": "VARCHAR(32) DEFAULT ''",
            "timeout_seconds": "FLOAT DEFAULT 0.0",
            "category_rules_json": "TEXT",
            "detail_policy_json": "TEXT",
            "cache_policy_json": "TEXT",
            "proxy_enabled": "BOOLEAN DEFAULT 0",
            "proxy_url": "VARCHAR(255) DEFAULT ''",
        }
        with engine.begin() as conn:
            for col_name, col_def in needed.items():
                if col_name not in existing_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE site_settings ADD COLUMN {col_name} {col_def}"))
                    except Exception:
                        pass

    if "activation_codes" in insp.get_table_names():
        existing_cols = {c["name"] for c in insp.get_columns("activation_codes")}
        if "max_devices" not in existing_cols:
            with engine.begin() as conn:
                try:
                    conn.execute(text("ALTER TABLE activation_codes ADD COLUMN max_devices INT NOT NULL DEFAULT 1"))
                except Exception:
                    conn.execute(text("ALTER TABLE activation_codes ADD COLUMN max_devices INTEGER DEFAULT 1"))


def table_names(engine: Engine) -> list[str]:
    return sorted(inspect(engine).get_table_names())


def database_url_safe(url: str) -> str:
    """把连接串里的密码打码，好让它能安全地打进日志和终端。

    不处理的话，一句 ``print(settings.database_url)`` 就把生产密码写进了日志。
    """
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    credentials, host = rest.rsplit("@", 1)
    if ":" not in credentials:
        return url
    user, _password = credentials.split(":", 1)
    return f"{scheme}://{user}:***@{host}"
