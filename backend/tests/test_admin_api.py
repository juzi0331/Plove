"""后台接口：管理员鉴权、总览、手动刷新；以及主动预热的实际行为。

鉴权这块要**负面**测：没配令牌、令牌错了、压根没带令牌，三种都必须进不来。
后台接口是整台机器的入口，漏一条就是一个洞。
"""

from __future__ import annotations

from app.api.deps import ADMIN_TOKEN_HEADER, get_settings
from app.cache.content import ContentCache
from app.crawler.guard import SiteGuard
from app.crawler.registry import SiteRegistry
from app.services.warmup_service import WarmupRunner
from tests.helpers import crawler_calls

ADMIN = "test-admin-token"
HEADERS = {ADMIN_TOKEN_HEADER: ADMIN}


def _enable_admin(app, token: str = ADMIN) -> None:
    """把后台令牌塞进这台 app 的配置里。"""
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"admin_token": token}
    )


# ------------------------------------------------------------------ 鉴权

def test_admin_is_off_until_a_token_is_configured(authed_client, fake_app):
    """**空令牌必须永远进不来** —— 否则忘配一个变量就等于后台裸奔。"""
    response = authed_client.get("/api/v1/admin/status", headers=HEADERS)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert "PLOVE_ADMIN_TOKEN" in response.json()["error"]["message"]


def test_admin_rejects_unknown_token(authed_client, fake_app):
    _enable_admin(fake_app)
    # 令牌一律用 ASCII：HTTP 头按 ascii/latin-1 编码，中文在发请求之前就炸了
    response = authed_client.get("/api/v1/admin/status", headers={ADMIN_TOKEN_HEADER: "guessed"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_admin_rejects_missing_token(authed_client, fake_app):
    _enable_admin(fake_app)
    assert authed_client.get("/api/v1/admin/status").status_code == 401


def test_admin_needs_no_device_token(anon_client, fake_app):
    """后台用的是**另一套凭证**：运维不应该先给自己发个激活码才能进后台。"""
    _enable_admin(fake_app)
    assert anon_client.get("/api/v1/admin/status", headers=HEADERS).status_code == 200


def test_openapi_declares_both_credentials(fake_app):
    """两套凭证必须真的是**两个** security scheme。

    踩到过的坑：``APIKeyHeader`` 不给 ``scheme_name`` 时用类名当 scheme 名，
    于是后声明的那个**直接覆盖**前一个 —— OpenAPI 里只剩一个，
    Swagger 里点内容接口会发后台令牌，于是每个请求都 401，
    而你会以为是自己的激活码错了。
    """
    schema = fake_app.openapi()
    schemes = schema["components"]["securitySchemes"]

    assert set(schemes) == {"DeviceToken", "AdminToken"}
    assert schemes["DeviceToken"]["name"] == "X-Device-Token"
    assert schemes["AdminToken"]["name"] == "X-Admin-Token"

    # 每个接口引用的是"哪一个"也要对
    assert schema["paths"]["/api/v1/sites"]["get"]["security"] == [{"DeviceToken": []}]
    assert schema["paths"]["/api/v1/admin/status"]["get"]["security"] == [{"AdminToken": []}]


# ------------------------------------------------------------------ 总览

def test_status_reports_cache_warmup_and_site_health(authed_client, fake_app):
    _enable_admin(fake_app)
    authed_client.get("/api/v1/sites/fake/home")  # 制造一点缓存

    body = authed_client.get("/api/v1/admin/status", headers=HEADERS).json()
    assert body["ok"] is True

    data = body["data"]
    assert data["env"] == "dev"
    assert data["cache"]["size"] >= 1
    assert data["cache"]["ttl"]["home"] > 0
    assert data["warmup"]["running"] is False
    assert data["warmup"]["last_reason"] is None, "还没预热过，不该编出一个时间"

    sites = {item["site"]: item for item in data["sites"]}
    assert sites["fake"]["state"] == "closed"
    assert sites["fake"]["failures"] == 0
    assert sites["fake"]["max_concurrency"] >= 1


def test_status_shows_a_tripped_breaker(authed_client, fake_app, monkeypatch):
    """后台要能一眼看出"这个源被我们熔断了" —— 这是最需要解释的状态。"""
    _enable_admin(fake_app)
    monkeypatch.setenv("FAKE_MODE", "error")

    for _ in range(5):  # 默认阈值就是 5
        authed_client.get("/api/v1/sites/fake/home")
    assert authed_client.get("/api/v1/sites/fake/home").status_code == 503

    sites = authed_client.get("/api/v1/admin/status", headers=HEADERS).json()["data"]["sites"]
    entry = sites[0]
    assert entry["state"] == "open"
    assert entry["failures"] >= entry["fail_threshold"]
    assert entry["retry_after"] > 0


def test_status_lists_sites_before_they_are_ever_used(authed_client, fake_app):
    """**运维打开后台时要能看到"这台机器上有哪些源"，而不是一张空表。**

    源的健康是懒建的（碰过才有），所以以前这里会返回空 —— 而那比没有这个页面更糟：
    它会让人以为"源都没了"。现在按目录扫，从不 fork 爬虫。
    """
    _enable_admin(fake_app)
    sites = authed_client.get("/api/v1/admin/status", headers=HEADERS).json()["data"]["sites"]

    assert [item["site"] for item in sites] == ["fake"], "__init__.py 不该被当成一个源"
    assert sites[0]["probed"] is False, "还没取过 meta"
    assert sites[0]["state"] == "closed"


def test_probed_flips_after_a_real_request(authed_client, fake_app):
    """把"新的守护"和"已验证过的源"分开。

    两者的 ``state`` 与 ``failures`` 完全一样，只看那两个字段会误以为源已经验过了。
    """
    _enable_admin(fake_app)
    authed_client.get("/api/v1/sites/fake/home")

    sites = authed_client.get("/api/v1/admin/status", headers=HEADERS).json()["data"]["sites"]
    assert sites[0]["probed"] is True


# ------------------------------------------------------------------ 手动刷新

def test_refresh_returns_immediately_by_default(authed_client, fake_app):
    """默认**不等待**：一轮预热要逐个请求源站，卡在 HTTP 请求里先超时的是反代。"""
    _enable_admin(fake_app)

    body = authed_client.post("/api/v1/admin/cache/refresh", headers=HEADERS).json()
    assert body["ok"] is True
    assert body["data"]["started"] is True
    assert body["data"]["message"]
    assert body["data"]["warmup"] is None, "默认不该等它跑完"


def test_refresh_does_not_stack_up(authed_client, fake_app):
    """连点五次"刷新"，不该同时跑五轮 —— 那等于把源站遍历五遍。"""
    _enable_admin(fake_app)
    results = [
        authed_client.post("/api/v1/admin/cache/refresh", headers=HEADERS).json()["data"]["started"]
        for _ in range(5)
    ]
    assert any(results), "至少要有一次真的启动"
    assert results.count(True) < 5, "只有第一次该启动，之后应被「已经在跑」挡住"


def test_refresh_with_wait_returns_the_result(authed_client, fake_app, crawler_counter):
    """``?wait=true`` 会跟着跑完 —— 给 curl 和运维手动操作用的。"""
    _enable_admin(fake_app)
    before = crawler_calls(crawler_counter, "home")

    body = authed_client.post(
        "/api/v1/admin/cache/refresh", params={"wait": "true"}, headers=HEADERS
    ).json()

    result = body["data"]["warmup"]
    assert body["data"]["started"] is True
    assert result["last_reason"] == "手动"
    assert result["last_finished_at"] is not None
    assert result["sites"][0]["site"] == "fake"
    assert result["sites"][0]["ok"] is True
    assert result["sites"][0]["home_items"] == 1
    assert crawler_calls(crawler_counter, "home") > before


# ------------------------------------------------------------------ 预热本体

def test_warmup_refreshes_and_fills_the_cache(fake_runner, crawler_counter):
    """预热要**换掉**旧值，不能只是读一遍缓存 —— 否则它什么也没做。"""
    registry = SiteRegistry(fake_runner, meta_ttl=0)
    cache = ContentCache(ttl_home=3600, ttl_category=3600, ttl_detail=3600)
    runner = WarmupRunner(registry, cache, max_categories=1)

    status = runner.run_once(reason="测试")
    assert status.last_reason == "测试"
    assert status.last_started_at is not None
    assert status.sites[0].ok is True
    assert status.sites[0].categories == 1
    assert crawler_calls(crawler_counter, "home") == 1

    # 第二次：缓存里本该有货，但 force 必须让它重新抓
    runner.run_once(reason="再来一次")
    assert crawler_calls(crawler_counter, "home") == 2, "拿到缓存就收工了，等于没预热"


def test_warmup_does_not_raise_when_a_site_is_broken(fake_runner, monkeypatch):
    """后台任务失败绝不能让服务崩 —— 结果记在 status 里，等后台看。"""
    monkeypatch.setenv("FAKE_MODE", "error")
    registry = SiteRegistry(fake_runner, meta_ttl=0)
    runner = WarmupRunner(registry, cache=ContentCache(), max_categories=1)

    status = runner.run_once(reason="测试")
    entry = status.sites[0]
    assert entry.ok is False
    assert entry.error and "UPSTREAM_BLOCKED" in entry.error


def test_warmup_respects_the_breaker(fake_runner, crawler_counter, monkeypatch):
    """熔断中的源**不该被每 24 小时的预热准点捅一次**。"""
    monkeypatch.setenv("FAKE_MODE", "error")
    registry = SiteRegistry(
        fake_runner,
        meta_ttl=0,
        guard_factory=lambda key: SiteGuard(key, fail_threshold=1, reset_seconds=3600),
    )
    runner = WarmupRunner(registry, cache=ContentCache(), max_categories=1)

    runner.run_once(reason="第一轮")  # 这一轮就把熔断打开了
    before = crawler_calls(crawler_counter, "home")

    status = runner.run_once(reason="第二轮")
    assert status.sites[0].ok is False
    assert "CIRCUIT_OPEN" in (status.sites[0].error or "")
    assert crawler_calls(crawler_counter, "home") == before, "熔断期还去抓了"


def test_warmup_job_is_off_by_default():
    """默认不开：它会在没人访问时也去请求源站，属于"默认打开会很意外"的事。"""
    from app.main import _start_warmup_job

    assert _start_warmup_job() is None
