#!/usr/bin/env python
"""建表 / 检查数据库连通性。

用法::

    python tools/init_db.py            # 建表（已存在的跳过），然后报表清单
    python tools/init_db.py --check    # 只连一下，报数据库版本与已有的表

真实环境的连接串写在 ``backend/.env`` 里，例如::

    PLOVE_DATABASE_URL=mysql+pymysql://plove:密码@192.168.1.10:3306/plove?charset=utf8mb4

密码在输出里会打码，可以放心把日志贴出去。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import force_utf8  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.schema import create_schema, database_url_safe, table_names  # noqa: E402
from app.db.session import get_engine  # noqa: E402


def _server_version(engine) -> str:
    dialect = engine.dialect.name
    statement = {"mysql": "SELECT VERSION()", "sqlite": "SELECT sqlite_version()"}.get(dialect)
    if statement is None:
        return "(未识别)"
    with engine.connect() as connection:
        return str(connection.exec_driver_sql(statement).scalar())


def main(argv: list[str] | None = None) -> int:
    force_utf8()
    parser = argparse.ArgumentParser(description="建表 / 检查数据库连通性")
    parser.add_argument("--check", action="store_true", help="只检查连通性，不建表")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    settings = get_settings()
    print(f"数据库 : {database_url_safe(settings.database_url)}")
    if settings.database_url.startswith("sqlite"):
        print("提示   : 这是本地 SQLite。真实环境请用 PLOVE_DATABASE_URL 指到 MySQL。")

    engine = get_engine()
    print(f"方言   : {engine.dialect.name}")

    try:
        print(f"版本   : {_server_version(engine)}")
    except Exception as exc:  # noqa: BLE001 - 连不上就是连不上，原样报给用户
        print(f"连不上 : {type(exc).__name__}: {exc}")
        return 1

    if args.check:
        existing = table_names(engine)
        print(f"已有的表: {', '.join(existing) if existing else '（空库）'}")
        return 0

    tables = create_schema(engine)
    print(f"建表完成，共 {len(tables)} 张: {', '.join(tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
