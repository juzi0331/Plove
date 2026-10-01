"""真连 MySQL 的测试 —— **默认跳过**。

存在的意义：本地的表结构是跑在 SQLite 上的，而线上是 MySQL。
两者大部分时候一致，但"大部分时候"正是事故的来源。所以留一个开关，
让你能拿**真库**验一遍建表与一次完整激活流程。

跑法::

    # PowerShell
    $env:PLOVE_TEST_DATABASE_URL="mysql+pymysql://用户:密码@主机:端口/plove_test?charset=utf8mb4"
    .\\.venv\\Scripts\\python.exe -m pytest -m mysql -v

    # Git Bash
    PLOVE_TEST_DATABASE_URL="..." ./.venv/Scripts/python.exe -m pytest -m mysql -v

**必须用一个单独的测试库**（比如 ``plove_test``），别指向 ``PLOVE_DATABASE_URL``
里那个开发/生产库 —— 这个测试会真的建表、真的写数据（虽然最后会清掉自己写的行）。
现在这个测试只会建表 + 写 / 删自己那两行，所以两者指向同一个库**暂时**不会出事。
但分隔靠命名就成立了，不靠纪律 —— 以后真出现 ``drop_all`` 或改表结构的用例时，
测试库和开发库同名就是那个"本地跑完数据没了"的经典事故。
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.db.schema import create_schema, table_names
from app.models.activation import ActivationCode
from app.models.device import Device
from app.services import activation_service

pytestmark = pytest.mark.mysql

TEST_DATABASE_URL = os.environ.get("PLOVE_TEST_DATABASE_URL", "")


@pytest.fixture()
def mysql_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("未设置 PLOVE_TEST_DATABASE_URL，跳过真实 MySQL 测试")

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        create_schema(engine)
    except Exception as exc:  # noqa: BLE001 - 连不上就明确报出来
        pytest.skip(f"连不上 MySQL，跳过: {type(exc).__name__}: {exc}")
    yield engine
    engine.dispose()


def test_schema_creates_on_mysql(mysql_engine):
    names = table_names(mysql_engine)
    assert "activation_codes" in names
    assert "devices" in names


def test_activation_roundtrip_on_mysql(mysql_engine):
    """在真库上跑一遍：发码 → 激活 → 心跳。"""
    factory = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)

    with factory() as session:
        record = activation_service.issue_code(session, duration_hours=1, note="mysql 用例")
        session.commit()
        activation_id = record.id

    try:
        with factory() as session:
            result = activation_service.redeem(session, code=record.code, device_name="mysql-测试机")
            session.commit()
            assert result.remaining_seconds > 0

        with factory() as session:
            state = activation_service.heartbeat(session, result.device_token)
            assert state.is_active is True
    finally:
        # 别在真库里留垃圾
        with factory() as session:
            session.execute(delete(Device).where(Device.activation_id == activation_id))
            session.execute(delete(ActivationCode).where(ActivationCode.id == activation_id))
            session.commit()
