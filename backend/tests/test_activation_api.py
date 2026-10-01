"""激活与会话接口。

这里把三条已确认的业务规则钉死：

1. 时长制，**从首次激活起算**，换设备不重置；
2. **一码多设备**（同一个码可以激活很多台）；
3. **但同时只能一台在线**，后来的顶掉先来的。
"""

from __future__ import annotations

from datetime import timedelta

from app.api.deps import DEVICE_TOKEN_HEADER
from app.core.clock import utcnow
from app.services import activation_service


def _issue(db_session, *, hours: int = 24) -> str:
    record = activation_service.issue_code(db_session, duration_hours=hours, note="测试")
    db_session.commit()
    return record.code


def _redeem(client, code: str, name: str = ""):
    response = client.post(
        "/api/v1/activation/redeem",
        json={"code": code, "device_name": name},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _heartbeat(client, token: str):
    response = client.post("/api/v1/activation/heartbeat", headers={DEVICE_TOKEN_HEADER: token})
    assert response.status_code == 200, response.text
    return response.json()["data"]


# ------------------------------------------------------------------ 激活


def test_redeem_with_valid_code(anon_client, db_session):
    data = _redeem(anon_client, _issue(db_session), "测试机")

    assert data["device_token"]
    assert data["device_name"] == "测试机"
    # 24 小时的码，刚激活应该还剩 23 小时以上
    assert data["remaining_seconds"] > 23 * 3600
    assert data["expires_at"].endswith("Z") or "+00:00" in data["expires_at"]
    assert data["heartbeat_interval_seconds"] == 30


def test_redeem_with_unknown_code(anon_client):
    response = anon_client.post("/api/v1/activation/redeem", json={"code": "PLV-AAAA-BBBB-CCCC"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACTIVATION_INVALID"


def test_redeem_with_nothing_is_reachable_without_auth(anon_client):
    """这条同时证明：**激活接口自己没有守卫** —— 否则没激活的人永远激活不了。"""
    response = anon_client.post("/api/v1/activation/redeem", json={})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACTIVATION_INVALID"


def test_code_input_tolerates_lowercase_and_spaces(anon_client, db_session):
    """用户是手打的码，小写、多空格、全角横线都得能认。"""
    code = _issue(db_session)
    messy = f"  {code.lower().replace('-', '－')}  "

    assert _redeem(anon_client, messy)["device_token"]


# ------------------------------------------------------------------ 一码多设备 / 单点在线


def test_second_device_kicks_the_first(anon_client, db_session):
    code = _issue(db_session)
    first = _redeem(anon_client, code, "设备1")
    second = _redeem(anon_client, code, "设备2")

    assert first["device_token"] != second["device_token"], "两台设备必须拿到不同的身份"

    assert _heartbeat(anon_client, first["device_token"])["is_active"] is False
    assert _heartbeat(anon_client, second["device_token"])["is_active"] is True


def test_kicked_device_can_claim_the_slot_back(anon_client, db_session):
    """被踢的设备只要再调一次 redeem（带自己的 token）就能抢回来 —— 这就是"在此设备继续"。"""
    code = _issue(db_session)
    first = _redeem(anon_client, code, "设备1")
    second = _redeem(anon_client, code, "设备2")

    response = anon_client.post(
        "/api/v1/activation/redeem", json={"device_token": first["device_token"]}
    )
    assert response.status_code == 200
    assert response.json()["data"]["device_token"] == first["device_token"]

    # 现在轮到设备2 被踢
    assert _heartbeat(anon_client, second["device_token"])["is_active"] is False
    assert _heartbeat(anon_client, first["device_token"])["is_active"] is True


def test_duration_is_not_reset_when_switching_devices(anon_client, db_session):
    """时长从**首次激活**起算。换设备只换活跃位，不动到期时间。"""
    code = _issue(db_session, hours=24)
    first = _redeem(anon_client, code, "设备1")
    second = _redeem(anon_client, code, "设备2")

    assert second["expires_at"] == first["expires_at"]
    assert abs(second["remaining_seconds"] - first["remaining_seconds"]) <= 2


# ------------------------------------------------------------------ 停用与到期


def test_disabled_code_cannot_activate(anon_client, db_session):
    from sqlalchemy import select

    from app.models.activation import ActivationCode

    code = _issue(db_session)
    row = db_session.scalar(select(ActivationCode).where(ActivationCode.code == code))
    row.disabled_at = utcnow()
    db_session.commit()

    response = anon_client.post("/api/v1/activation/redeem", json={"code": code})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_expired_code_cannot_activate(anon_client, db_session):
    from sqlalchemy import select

    from app.models.activation import ActivationCode

    code = _issue(db_session)
    row = db_session.scalar(select(ActivationCode).where(ActivationCode.code == code))
    row.activated_at = utcnow() - timedelta(hours=48)
    row.expires_at = utcnow() - timedelta(hours=24)
    db_session.commit()

    response = anon_client.post("/api/v1/activation/redeem", json={"code": code})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACTIVATION_EXPIRED"


def test_expired_code_stops_browsing_too(anon_client, db_session):
    """到期之后连内容都拿不到，不只是不能重新激活。"""
    code = _issue(db_session)
    data = _redeem(anon_client, code)

    from sqlalchemy import select

    from app.models.activation import ActivationCode

    row = db_session.scalar(select(ActivationCode).where(ActivationCode.code == code))
    row.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    response = anon_client.get(
        "/api/v1/sites", headers={DEVICE_TOKEN_HEADER: data["device_token"]}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACTIVATION_EXPIRED"
