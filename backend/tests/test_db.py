"""数据库地基与时间工具。"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.clock import as_aware, utcnow
from app.db.schema import database_url_safe, table_names
from app.services.activation_service import generate_code, normalize_code


def test_schema_creates_the_expected_tables(db_engine):
    names = table_names(db_engine)
    assert "activation_codes" in names
    assert "devices" in names


def test_database_url_password_is_masked():
    """日志里绝不能出现明文密码。"""
    masked = database_url_safe("mysql+pymysql://plove:super-secret@192.168.1.10:3306/plove")
    assert masked == "mysql+pymysql://plove:***@192.168.1.10:3306/plove"
    assert "super-secret" not in masked


def test_database_url_without_password_is_untouched():
    url = "sqlite+pysqlite:///E:/tmp/plove.db"
    assert database_url_safe(url) == url


def test_utcnow_is_naive_utc():
    """写库的一律是 naive UTC —— MySQL 的 DATETIME 不带时区。"""
    now = utcnow()
    assert now.tzinfo is None
    delta = abs((now - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
    assert delta < 5


def test_as_aware_marks_utc():
    """出接口的一律是 aware UTC，客户端才知道那是 UTC。"""
    aware = as_aware(datetime(2026, 1, 1, 12, 0, 0))
    assert aware.tzinfo is timezone.utc
    assert as_aware(None) is None


def test_generated_codes_are_unique_and_readable():
    codes = {generate_code() for _ in range(200)}
    assert len(codes) == 200, "生成 200 个码不该撞车"

    sample = codes.pop()
    assert sample.startswith("PLV-")
    assert len(sample) == 18  # PLV-XXXX-XXXX-XXXX
    # 容易看错的字符一个都不许出现
    assert not set(sample[4:]) & set("IO01")


def test_normalize_code_tolerates_hand_typed_input():
    assert normalize_code(" plv-a7k2-m9qp-3xzt ") == "PLV-A7K2-M9QP-3XZT"
    assert normalize_code("PLV－A7K2－M9QP－3XZT") == "PLV-A7K2-M9QP-3XZT"
    assert normalize_code("PLV A7K2 M9QP 3XZT") == "PLVA7K2M9QP3XZT"
