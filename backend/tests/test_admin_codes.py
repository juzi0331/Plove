"""后台的**动作**类接口：发码、停用、解封、延长、看设备、踢设备。

这些接口和 ``test_admin_api.py`` 里那些\"看一眼\"的接口性质完全不同：

* 看一眼错了只是显示不对；
* **动手指令错了会直接影响用户** —— 封错一个码、踢错一台设备，
  对方那边**不会收到任何解释**，只会突然看不了。

所以这里的断言重点不是\"接口返回 200\"，而是**副作用是否精确**：
停用之后客户端立刻拿不到内容、但设备还认得自己；
踢下线之后那台会被停播、**但它还能自己抢回来**（踢不是封）。

还有一个贯穿全文件的安全断言：**设备令牌的明文绝不能出现在任何后台响应里**。
"""

from __future__ import annotations

from app.api.deps import ADMIN_TOKEN_HEADER, get_settings
from tests.helpers import crawler_calls  # noqa: F401  (保持和别的测试同样的导入面)

ADMIN = "test-admin-token"
HEADERS = {ADMIN_TOKEN_HEADER: ADMIN}


def _enable_admin(app, token: str = ADMIN) -> None:
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"admin_token": token}
    )


def _find(client, code: str) -> dict:
    """从列表里翻出某个码。**走接口而不是直接查库** —— 这样列表的字段口径也被顺带验了。"""
    body = client.get("/api/v1/admin/codes", params={"query": code}, headers=HEADERS).json()
    assert body["ok"] is True
    for item in body["data"]["codes"]:
        if item["code"] == code:
            return item
    raise AssertionError(f"列表里没有找到 {code}：{body}")


# ------------------------------------------------------------------ 列表


def test_codes_are_listed_with_real_usage(authed_client, fake_app, activation):
    """列表要能回答\"这个码被谁在用\"，而不只是把表 dump 出来。"""
    _enable_admin(fake_app)

    item = _find(authed_client, activation["code"])
    assert item["duration_hours"] == 24
    assert item["note"] == "测试"
    assert item["activated_at"] is not None, "已经激活过，这里必须有时间"
    assert item["expires_at"] is not None
    assert item["disabled_at"] is None
    assert item["remaining_seconds"] > 0
    assert item["device_count"] == 1
    assert item["active_device_name"] == "测试机"


def test_search_matches_note_and_code_case_insensitively(authed_client, fake_app, activation):
    """运维找码时记得的往往是备注（发给谁），而不是那串字符。"""
    _enable_admin(fake_app)

    by_note = authed_client.get(
        "/api/v1/admin/codes", params={"query": "测试"}, headers=HEADERS
    ).json()["data"]
    assert any(item["code"] == activation["code"] for item in by_note["codes"])

    # 码一律存成大写，搜小写也该命中
    lower = activation["code"].lower()
    by_lower = authed_client.get(
        "/api/v1/admin/codes", params={"query": lower}, headers=HEADERS
    ).json()["data"]
    assert any(item["code"] == activation["code"] for item in by_lower["codes"])


def test_list_reports_total_not_page_size(authed_client, fake_app):
    _enable_admin(fake_app)
    authed_client.post(
        "/api/v1/admin/codes", json={"days": 1, "count": 3, "note": "分页"}, headers=HEADERS
    )

    page = authed_client.get(
        "/api/v1/admin/codes", params={"page": 1, "page_size": 2}, headers=HEADERS
    ).json()["data"]
    assert page["page_size"] == 2
    assert len(page["codes"]) == 2
    assert page["total"] >= 4, "total 是满足条件的总数，不受分页影响"


# ------------------------------------------------------------------ 发码


def test_issue_codes_returns_codes_that_actually_work(anon_client, authed_client, fake_app):
    """发出去的码必须**当场能用** —— 否则\"发出去了\"只是看起来成功了。"""
    _enable_admin(fake_app)

    body = authed_client.post(
        "/api/v1/admin/codes",
        json={"days": 7, "count": 2, "note": "第一批"},
        headers=HEADERS,
    ).json()
    assert body["ok"] is True
    data = body["data"]
    assert len(data["codes"]) == 2
    assert len(set(data["codes"])) == 2, "发出来的码不能重复"
    assert data["duration_hours"] == 7 * 24
    assert data["note"] == "第一批"

    # 全新的码：还没计时，所以没有到期时间
    item = _find(authed_client, data["codes"][0])
    assert item["activated_at"] is None
    assert item["expires_at"] is None
    assert item["remaining_seconds"] == 0, "0 在这里的含义是「还没开始」，要靠 activated_at 区分"
    assert item["device_count"] == 0

    # 真的去激活一次
    redeemed = anon_client.post(
        "/api/v1/activation/redeem",
        json={"code": data["codes"][0], "device_name": "新设备"},
    ).json()
    assert redeemed["ok"] is True
    assert redeemed["data"]["remaining_seconds"] > 6 * 24 * 3600


def test_issue_codes_needs_exactly_one_duration(authed_client, fake_app):
    _enable_admin(fake_app)

    assert authed_client.post("/api/v1/admin/codes", json={}, headers=HEADERS).status_code == 422
    both = authed_client.post(
        "/api/v1/admin/codes", json={"hours": 1, "days": 1}, headers=HEADERS
    )
    assert both.status_code == 422


# ------------------------------------------------------------------ 停用 / 解封


def test_disable_takes_effect_on_the_very_next_request(anon_client, authed_client, fake_app, activation):
    """停用必须**立刻**生效，不能等重启、也不能等心跳周期。

    三种入口都要一起拦：内容接口、心跳、以及拿同一个码再激活一次。
    漏一个就等于\"封了但没封死\"。
    """
    _enable_admin(fake_app)
    item = _find(authed_client, activation["code"])

    disabled = authed_client.post(
        f"/api/v1/admin/codes/{item['id']}/disable", headers=HEADERS
    ).json()
    assert disabled["data"]["code"]["disabled_at"] is not None

    blocked = authed_client.get("/api/v1/sites")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "FORBIDDEN"

    assert authed_client.post("/api/v1/activation/heartbeat").status_code == 403
    assert (
        anon_client.post(
            "/api/v1/activation/redeem",
            json={"code": activation["code"], "device_name": "别人"},
        ).status_code
        == 403
    )


def test_enable_gives_it_back(authed_client, fake_app, activation):
    _enable_admin(fake_app)
    item = _find(authed_client, activation["code"])

    authed_client.post(f"/api/v1/admin/codes/{item['id']}/disable", headers=HEADERS)
    assert authed_client.get("/api/v1/sites").status_code == 403

    again = authed_client.post(f"/api/v1/admin/codes/{item['id']}/enable", headers=HEADERS).json()
    assert again["data"]["code"]["disabled_at"] is None
    assert authed_client.get("/api/v1/sites").status_code == 200


# ------------------------------------------------------------------ 延长


def test_extend_moves_expiry_for_an_activated_code(authed_client, fake_app, activation):
    """**这条盯的是一个非常容易写错的地方。**

    码一旦激活，``expires_at`` 就钉死了，改 ``duration_hours`` 对它完全无效 ——
    必须给 ``expires_at`` 加时间。实现如果写错，界面上会显示\"已延长\"，
    而用户那边**一点变化都没有**。
    """
    _enable_admin(fake_app)
    before = _find(authed_client, activation["code"])

    after = authed_client.post(
        f"/api/v1/admin/codes/{before['id']}/extend",
        json={"hours": 48},
        headers=HEADERS,
    ).json()["data"]["code"]

    assert after["remaining_seconds"] - before["remaining_seconds"] >= 48 * 3600 - 5
    assert after["duration_hours"] == before["duration_hours"], (
        "已激活的码改 duration_hours 是没有意义的，它只是历史记录"
    )
    assert after["expires_at"] > before["expires_at"]


def test_extend_adds_to_duration_for_an_unused_code(authed_client, fake_app):
    """还没激活的码相反：它还没有到期时间，只能加时长。"""
    _enable_admin(fake_app)
    issued = authed_client.post(
        "/api/v1/admin/codes", json={"days": 1, "count": 1}, headers=HEADERS
    ).json()["data"]["codes"][0]

    item = _find(authed_client, issued)
    after = authed_client.post(
        f"/api/v1/admin/codes/{item['id']}/extend",
        json={"hours": 24},
        headers=HEADERS,
    ).json()["data"]["code"]

    assert after["duration_hours"] == 48
    assert after["expires_at"] is None


def test_extend_does_not_silently_unban(authed_client, fake_app, activation):
    """延长和停用是两件事。延长一个被停用的码，**不该顺手把它解封**。"""
    _enable_admin(fake_app)
    item = _find(authed_client, activation["code"])
    authed_client.post(f"/api/v1/admin/codes/{item['id']}/disable", headers=HEADERS)

    after = authed_client.post(
        f"/api/v1/admin/codes/{item['id']}/extend",
        json={"hours": 1},
        headers=HEADERS,
    ).json()["data"]["code"]
    assert after["disabled_at"] is not None


def test_missing_code_is_a_404(authed_client, fake_app):
    _enable_admin(fake_app)
    response = authed_client.post(
        "/api/v1/admin/codes/999999/extend", json={"hours": 1}, headers=HEADERS
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ------------------------------------------------------------------ 设备


def test_devices_never_leak_the_token(authed_client, fake_app, activation):
    """**设备令牌是客户端凭证，等于密码。**

    后台只需要能区分\"是哪一台\"，所以只给前 6 位。
    这条断言是整份文件里最重要的一条：它挡的是\"顺手把明文也返回了吧\"这种改动。
    """
    _enable_admin(fake_app)
    item = _find(authed_client, activation["code"])

    response = authed_client.get(f"/api/v1/admin/codes/{item['id']}/devices", headers=HEADERS)
    body = response.json()
    assert body["ok"] is True

    devices = body["data"]["devices"]
    assert len(devices) == 1
    assert devices[0]["name"] == "测试机"
    assert devices[0]["is_active"] is True
    assert devices[0]["token_prefix"] == activation["token"][:6]
    assert activation["token"] not in response.text, "令牌明文泄露到后台响应里了"


def test_kick_offline_but_not_banned(authed_client, anon_client, fake_app, activation):
    """踢设备的**精确语义**：

    * 那台立刻被停播（内容接口 ``SESSION_KICKED``、心跳 ``is_active=false``）；
    * 但**它还能自己抢回来** —— 踢是\"请下线\"，不是\"封设备\"。
      真要禁掉一个人，应该停用整个码。
    """
    _enable_admin(fake_app)
    item = _find(authed_client, activation["code"])
    device_id = authed_client.get(
        f"/api/v1/admin/codes/{item['id']}/devices", headers=HEADERS
    ).json()["data"]["devices"][0]["id"]

    kicked = authed_client.post(f"/api/v1/admin/devices/{device_id}/kick", headers=HEADERS).json()
    assert kicked["ok"] is True
    assert kicked["data"]["code"]["active_device_name"] is None

    # 内容接口：409 SESSION_KICKED（不是 401 —— 令牌还是有效的，只是不在活跃位上）
    blocked = authed_client.get("/api/v1/sites")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SESSION_KICKED"

    # 心跳要如实汇报，客户端才能停下来提示用户
    state = authed_client.post("/api/v1/activation/heartbeat").json()["data"]
    assert state["is_active"] is False

    # 还能抢回来：这就是\"踢\"和\"封\"的分界
    back = anon_client.post(
        "/api/v1/activation/redeem",
        json={"device_token": activation["token"], "device_name": "测试机"},
    )
    assert back.status_code == 200
    assert authed_client.get("/api/v1/sites").status_code == 200


def test_kick_a_never_seen_device_is_a_404(authed_client, fake_app):
    _enable_admin(fake_app)
    assert authed_client.post("/api/v1/admin/devices/999999/kick", headers=HEADERS).status_code == 404


# ------------------------------------------------------------------ 鉴权（写接口要单独盯一遍）


def test_write_endpoints_are_guarded(anon_client, fake_app):
    """读接口测过不代表写接口就安全 —— 守卫挂在 router 上，但**新接口是手写的**。

    注意两种拒绝的含义不同，别把它们混成一种：

    * **还没配令牌** → 403，后台整体关闭（下一用例盯着它）；
    * **配了但没带 / 带错** → 401。
    """
    assert anon_client.post("/api/v1/admin/codes", json={"days": 1}).status_code == 403

    _enable_admin(fake_app)
    assert anon_client.post("/api/v1/admin/codes", json={"days": 1}).status_code == 401
    assert (
        anon_client.post(
            "/api/v1/admin/codes", json={"days": 1}, headers={ADMIN_TOKEN_HEADER: "guessed"}
        ).status_code
        == 401
    )
    assert anon_client.get("/api/v1/admin/codes").status_code == 401


def test_write_endpoints_refuse_when_no_token_configured(anon_client, fake_app):
    """空令牌 = 后台整体关闭（403），这条对写接口尤其要紧。"""
    response = anon_client.post("/api/v1/admin/codes", json={"days": 1}, headers=HEADERS)
    assert response.status_code == 403
    assert "PLOVE_ADMIN_TOKEN" in response.json()["error"]["message"]
