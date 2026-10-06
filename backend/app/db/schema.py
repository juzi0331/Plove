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
            "proxy_node_id": "VARCHAR(64) DEFAULT ''",
        }
        with engine.begin() as conn:
            for col_name, col_def in needed.items():
                if col_name not in existing_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE site_settings ADD COLUMN {col_name} {col_def}"))
                    except Exception:
                        pass

            # 若为 MySQL / MariaDB，自动扩容 JSON 字段为 MEDIUMTEXT，根治多分类超出 4096 字符截断与报错
            if engine.dialect.name == "mysql":
                for col_name in ("category_rules_json", "detail_policy_json", "cache_policy_json"):
                    try:
                        conn.execute(text(f"ALTER TABLE site_settings MODIFY COLUMN {col_name} MEDIUMTEXT"))
                    except Exception:
                        pass

    if "system_settings" in insp.get_table_names():
        if engine.dialect.name == "mysql":
            with engine.begin() as conn:
                try:
                    conn.execute(text("ALTER TABLE system_settings MODIFY COLUMN value_json MEDIUMTEXT"))
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
        if "code_hash" not in existing_cols:
            with engine.begin() as conn:
                try:
                    conn.execute(text("ALTER TABLE activation_codes ADD COLUMN code_hash VARCHAR(64) NULL"))
                    conn.execute(text("CREATE INDEX ix_activation_codes_code_hash ON activation_codes(code_hash)"))
                except Exception:
                    pass

    if "devices" in insp.get_table_names():
        existing_cols = {c["name"] for c in insp.get_columns("devices")}
        needed_dev = {
            "is_playing": "BOOLEAN DEFAULT 0",
            "current_vod_title": "VARCHAR(255) DEFAULT ''",
            "last_playback_at": "DATETIME NULL",
        }
        with engine.begin() as conn:
            for col_name, col_def in needed_dev.items():
                if col_name not in existing_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE devices ADD COLUMN {col_name} {col_def}"))
                    except Exception:
                        pass

    if "playback_records" not in insp.get_table_names():
        with engine.begin() as conn:
            # 兼容 SQLite 与 MySQL 的轻量建表保底
            try:
                if engine.dialect.name == "sqlite":
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS playback_records (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            device_id INTEGER NOT NULL,
                            activation_id INTEGER NOT NULL,
                            vod_id VARCHAR(64) NOT NULL,
                            vod_name VARCHAR(255) DEFAULT '',
                            vod_pic VARCHAR(512) DEFAULT '',
                            ep_name VARCHAR(120) DEFAULT '',
                            site_key VARCHAR(64) DEFAULT '',
                            position FLOAT DEFAULT 0.0,
                            duration FLOAT DEFAULT 0.0,
                            progress_percent INTEGER DEFAULT 0,
                            is_playing BOOLEAN DEFAULT 1,
                            created_at DATETIME,
                            updated_at DATETIME,
                            CONSTRAINT uq_device_vod UNIQUE (device_id, vod_id)
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS playback_records (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            device_id INT NOT NULL,
                            activation_id INT NOT NULL,
                            vod_id VARCHAR(64) NOT NULL,
                            vod_name VARCHAR(255) DEFAULT '',
                            vod_pic VARCHAR(512) DEFAULT '',
                            ep_name VARCHAR(120) DEFAULT '',
                            site_key VARCHAR(64) DEFAULT '',
                            position FLOAT DEFAULT 0.0,
                            duration FLOAT DEFAULT 0.0,
                            progress_percent INT DEFAULT 0,
                            is_playing BOOLEAN DEFAULT 1,
                            created_at DATETIME,
                            updated_at DATETIME,
                            UNIQUE KEY uq_device_vod (device_id, vod_id),
                            INDEX ix_playback_records_device_id (device_id),
                            INDEX ix_playback_records_activation_id (activation_id),
                            INDEX ix_playback_records_vod_id (vod_id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """))
            except Exception:
                pass


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
