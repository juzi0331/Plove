"""激活码哈希化、写节流与并发边界测试。"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.clock import utcnow
from app.core.errors import AppError, ErrorCode
from app.db.base import Base
from app.models.activation import ActivationCode
from app.models.device import Device
from app.services import activation_service
from app.services.activation_service import hash_code, issue_code, redeem, require_active


@pytest.fixture
def sqlite_db_session(tmp_path):
    db_file = tmp_path / "test_concurrency.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    session = SessionLocal()
    try:
        yield session, SessionLocal
    finally:
        session.close()
        engine.dispose()


def test_code_hash_and_legacy_backfill(sqlite_db_session):
    session, _ = sqlite_db_session

    # 1. 签发新码时，自动生成 code_hash
    code_record = issue_code(session, duration_hours=24, note="测试哈希发码")
    assert code_record.code_hash is not None
    assert code_record.code_hash == hash_code(code_record.code)

    # 2. 正常通过 code 激活（内部走 hash 索引命中）
    res = redeem(session, code=code_record.code, device_name="DeviceA")
    assert res.device_token is not None

    # 3. 模拟老版本迁移前数据：code_hash 为空的老码
    raw_code = "PLV-LEGACY-CODE-0001"
    legacy_record = ActivationCode(
        code=raw_code,
        code_hash=None,
        duration_hours=12,
        max_devices=1,
    )
    session.add(legacy_record)
    session.flush()
    assert legacy_record.code_hash is None

    # 4. 激活老码：回退明文查库命中，并自动把 code_hash 补齐落库
    res_legacy = redeem(session, code=raw_code, device_name="DeviceB")
    assert res_legacy.device_token is not None
    assert legacy_record.code_hash == hash_code(raw_code)


def test_require_active_last_seen_throttling(sqlite_db_session):
    session, _ = sqlite_db_session

    code_record = issue_code(session, duration_hours=24)
    res = redeem(session, code=code_record.code, device_name="Device1")
    token = res.device_token

    # 首次校验
    device = require_active(session, token)
    first_seen = device.last_seen_at
    assert first_seen is not None

    # 模拟短时间连续访问（5秒内多次请求）：last_seen_at 被内存节流，不触发写放大
    device.last_seen_at = first_seen
    device_again = require_active(session, token)
    assert device_again.last_seen_at == first_seen

    # 模拟距离上次更新已超过 60 秒：触发刷新写入
    device.last_seen_at = utcnow() - timedelta(seconds=65)
    old_time = device.last_seen_at
    device_updated = require_active(session, token)
    assert device_updated.last_seen_at > old_time


def test_max_devices_limit_and_error_message(sqlite_db_session):
    session, _ = sqlite_db_session

    # 限制最多只能绑定 1 台设备
    record = issue_code(session, duration_hours=24, max_devices=1)

    # 设备 1 激活绑定成功
    redeem(session, code=record.code, device_name="Phone1")

    # 设备 2 尝试接入新设备：应当被拒绝，文案收敛不泄露策略数字
    with pytest.raises(AppError) as exc_info:
        redeem(session, code=record.code, device_name="Phone2")

    assert exc_info.value.code == ErrorCode.ACTIVATION_INVALID
    assert "无法接入新设备" in exc_info.value.message
    # 断言报错文案中不含有策略数字明文（如 '上限 1 台'）
    assert "1" not in exc_info.value.message


def test_sqlite_concurrent_redeem_max_devices(sqlite_db_session):
    _, SessionLocal = sqlite_db_session

    # 初始化一个 max_devices=1 的码
    init_session = SessionLocal()
    record = issue_code(init_session, duration_hours=24, max_devices=1)
    init_session.commit()
    target_code = record.code
    init_session.close()

    successes = []
    failures = []

    def try_redeem(worker_id: int):
        worker_session = SessionLocal()
        try:
            res = redeem(worker_session, code=target_code, device_name=f"Device-{worker_id}")
            worker_session.commit()
            return True, None
        except Exception as exc:
            worker_session.rollback()
            return False, exc
        finally:
            worker_session.close()

    # 10 个线程并发尝试接入该激活码
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_redeem, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            ok, exc = f.result()
            if ok:
                successes.append(True)
            else:
                failures.append(exc)

    check_session = SessionLocal()
    bound_count = check_session.scalar(
        select(func.count(Device.id)).where(Device.activation_id == record.id)
    )
    check_session.close()

    # 绑定设备数绝不能超过 max_devices (1)
    assert bound_count <= 1
