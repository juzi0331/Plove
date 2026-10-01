"""公共夹具。

四套东西组合起来，整个后端就能**不联网、不碰真数据库**地测完：

* ``db_engine``  —— 每个用例一个独立的临时 SQLite 文件
* ``fake_*``     —— 爬虫目录指向 ``tests/fixtures/fake_crawler``
* ``anon_client``  —— 没激活的客户端
* ``authed_client``—— 已激活、带设备令牌的客户端
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# ⚠️ 必须在导入 app 之前设好。
#
# ``app.main`` 在**导入时**就调了一次 ``create_app()``（模块级 ``app = ...``），
# 那一下会读到缓存起来的配置。所以任何 fixture 里的 monkeypatch 都来不及 ——
# 如果开发者本机的 ``.env`` 打开了主动预热，测试期间就会真的定时去请求源站。
# 环境变量优先级高于 .env，因此这一行能让测试永远不跑后台预热任务。
os.environ.setdefault("PLOVE_WARMUP_ENABLED", "false")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.deps import DEVICE_TOKEN_HEADER, get_db, reset_runtime  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.crawler.runner import CrawlerRunner  # noqa: E402
from app.db.schema import create_schema  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import activation_service  # noqa: E402

#: 假爬虫的"仓库根"，结构要和真的 crawler/ 一致（下面有 sites/）
FAKE_CRAWLER_DIR = Path(__file__).resolve().parent / "fixtures" / "fake_crawler"


# ------------------------------------------------------------------ 应用

@pytest.fixture()
def client():
    """用真实配置的客户端。只该用来打不碰数据库、不碰爬虫的接口（如健康检查）。"""
    with TestClient(create_app()) as test_client:
        yield test_client


# ------------------------------------------------------------------ 数据库

@pytest.fixture()
def db_engine(tmp_path):
    """每个用例一个**临时 SQLite 文件**。

    刻意不用内存库：内存库要多会话共享同一个连接（``StaticPool``），
    而共享同一个 DBAPI 连接会让两个 Session 互相干扰，出问题极难排查。
    临时文件没这个毛病，而且和线上一样是"真的落盘、真的提交"。
    """
    url = f"sqlite+pysqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    create_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db_session(db_factory):
    """给测试直接准备数据用。"""
    session = db_factory()
    try:
        yield session
    finally:
        session.close()


# ------------------------------------------------------------------ 组合

@pytest.fixture()
def fake_settings() -> Settings:
    """超时压到 2 秒，这样超时用例不用真的等 10 秒。

    ``admin_token`` 在这里**显式钉成空**，而不是让它去读 ``backend/.env``：
    本机装了后台面板的人，``.env`` 里一定配了 ``PLOVE_ADMIN_TOKEN``（不配就用不了面板），
    而"空令牌 = 后台整体 403"是必须测的**负面用例** —— 不钉死的话，
    这几个用例会随开发机的配置变红，而它们守的正是最要紧的那条安全默认值。
    需要令牌的用例自己用 ``_enable_admin`` 覆盖。

    请注意这条规矩：**测试不能依赖开发机上的 ``.env``。**
    """
    return Settings(
        crawler_dir=FAKE_CRAWLER_DIR,
        crawler_timeout=2.0,
        crawler_timeout_play=1.0,
        admin_token="",
    )


@pytest.fixture()
def fake_runner(fake_settings: Settings) -> CrawlerRunner:
    return CrawlerRunner(
        fake_settings.sites_dir,
        timeout=fake_settings.crawler_timeout,
        timeout_play=fake_settings.crawler_timeout_play,
    )


def _override_get_db(factory):
    """替掉真实数据库：请求用测试引擎，事务边界和线上保持一致。"""

    def _get_db():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _get_db


@pytest.fixture()
def fake_app(fake_settings: Settings, db_factory):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: fake_settings
    app.dependency_overrides[get_db] = _override_get_db(db_factory)
    # 注册表（meta + 每站守护）和内容缓存都是**进程内单例**，不清会串到别的用例：
    # 上一个用例缓存的 payload、熔断计数，都会变成下一个用例的"幽灵"。
    reset_runtime()
    yield app
    app.dependency_overrides.clear()
    reset_runtime()


def _client(app, token: str | None = None) -> TestClient:
    headers = {DEVICE_TOKEN_HEADER: token} if token else {}
    return TestClient(app, headers=headers)


@pytest.fixture()
def anon_client(fake_app):
    """**没有**激活令牌的客户端 —— 用来验"没激活就进不来"。"""
    with _client(fake_app) as test_client:
        yield test_client


@pytest.fixture()
def activation(db_session) -> dict:
    """签发一个码并激活一台设备，返回码与设备令牌。"""
    record = activation_service.issue_code(db_session, duration_hours=24, note="测试")
    db_session.commit()
    result = activation_service.redeem(db_session, code=record.code, device_name="测试机")
    db_session.commit()
    return {"code": record.code, "token": result.device_token}


@pytest.fixture()
def authed_client(fake_app, activation):
    """已激活的客户端，所有请求自动带上 ``X-Device-Token``。"""
    with _client(fake_app, activation["token"]) as test_client:
        yield test_client


# ------------------------------------------------------------------ 数调用次数

@pytest.fixture()
def crawler_counter(tmp_path, monkeypatch) -> Path:
    """让假爬虫把每次被调用的命令名记到一个文件里。

    数次数用 :func:`tests.helpers.crawler_calls`。
    缓存和 singleflight 都只能靠"真跑了几次"来验证 —— 这两件事的特点就是
    **响应长得一模一样**，从结果上是看不出来的。
    """
    path = tmp_path / "crawler-calls.txt"
    monkeypatch.setenv("FAKE_COUNTER", str(path))
    return path
