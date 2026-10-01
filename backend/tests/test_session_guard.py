"""会话守卫：没激活就进不来，被踢了就 409。

这层是"防泄露"的第一道门 —— 没有它，后端就是一个谁都能用的开放代理。
"""

from __future__ import annotations

from sqlalchemy import select

from app.api.deps import DEVICE_TOKEN_HEADER
from app.models.device import Device

#: 所有需要守卫的接口（每加一个内容接口都应该在这里补一条）
GUARDED_PATHS = (
    "/api/v1/sites",
    "/api/v1/sites/fake",
    "/api/v1/sites/fake/home",
    "/api/v1/sites/fake/category",
    "/api/v1/sites/fake/detail?vod_id=1",
    "/api/v1/sites/fake/playback?vod_id=1&ep=1",
)


def test_guarded_endpoints_reject_anonymous(anon_client):
    for path in GUARDED_PATHS:
        response = anon_client.get(path)
        assert response.status_code == 401, f"{path} 竟然没被守卫拦住"
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_unknown_token_is_rejected(anon_client):
    # 注意令牌必须是 ASCII —— HTTP 头装不下非 ASCII 字符，拿中文当令牌会在客户端就炸
    response = anon_client.get("/api/v1/sites", headers={DEVICE_TOKEN_HEADER: "not-a-real-token"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_active_device_can_browse(authed_client):
    assert authed_client.get("/api/v1/sites").status_code == 200
    assert authed_client.get("/api/v1/sites/fake/home").json()["ok"] is True


def test_kicked_device_gets_409_not_401(anon_client, activation):
    """被踢和没激活要**分开报**，否则前端分不清"该重新激活"还是"被顶了"。"""
    anon_client.post("/api/v1/activation/redeem", json={"code": activation["code"]})

    response = anon_client.get(
        "/api/v1/sites", headers={DEVICE_TOKEN_HEADER: activation["token"]}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_KICKED"


def test_heartbeat_is_not_guarded(anon_client):
    """心跳接口不能被守卫拦住，否则被踢的设备连"自己被踢了"都问不到。"""
    response = anon_client.post("/api/v1/activation/heartbeat")
    # 缺令牌报 401，但那是业务校验，不是守卫拦的（守卫拦会返回同样的码，所以这里查消息）
    assert response.status_code == 401
    assert "激活" in response.json()["error"]["message"]


def test_guard_result_is_discarded_by_the_router(authed_client):
    """守卫只负责放行/拒绝，路由签名里不该看到它返回的 Device。"""
    response = authed_client.get("/api/v1/sites")
    assert response.json()["data"]["sites"][0]["key"] == "fake"


def test_content_guard_does_not_write_last_seen(authed_client, activation, db_session):
    """内容请求只鉴权；在线时间只由 heartbeat 更新，避免并发播放时 SQLite 写锁。"""
    device = db_session.scalar(select(Device).where(Device.token == activation["token"]))
    assert device is not None
    before = device.last_seen_at

    response = authed_client.get("/api/v1/sites")
    assert response.status_code == 200

    db_session.expire_all()
    refreshed = db_session.scalar(select(Device).where(Device.token == activation["token"]))
    assert refreshed is not None
    assert refreshed.last_seen_at == before
