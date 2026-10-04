"""设备播放心跳与观看历史自动化测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ADMIN_TOKEN_HEADER, DEVICE_TOKEN_HEADER, get_settings

ADMIN = "test-admin-token"
ADMIN_HEADERS = {ADMIN_TOKEN_HEADER: ADMIN}


def _enable_admin(app, token: str = ADMIN) -> None:
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"admin_token": token}
    )


def test_playback_heartbeat_and_device_history(anon_client: TestClient, fake_app):
    _enable_admin(fake_app)
    client = anon_client
    # 1. 管理员发码
    res = client.post(
        "/api/v1/admin/codes",
        headers=ADMIN_HEADERS,
        json={"hours": 24, "count": 1, "note": "测试码"},
    )
    assert res.status_code == 200
    code = res.json()["data"]["codes"][0]

    # 2. 用户设备激活
    redeem_res = client.post(
        "/api/v1/activation/redeem",
        json={"code": code, "device_name": "客厅电视"},
    )
    assert redeem_res.status_code == 200
    device_token = redeem_res.json()["data"]["device_token"]
    dev_headers = {DEVICE_TOKEN_HEADER: device_token}

    # 3. 初始状态：已激活但未播放
    codes_res = client.get("/api/v1/admin/codes", headers=ADMIN_HEADERS)
    assert codes_res.status_code == 200
    c_item = next(c for c in codes_res.json()["data"]["codes"] if c["code"] == code)
    code_id = c_item["id"]
    assert c_item["device_count"] == 1
    assert c_item["is_online"] is True
    assert c_item["is_playing"] is False
    assert c_item["current_playback"] is None

    # 4. 获取设备 ID
    devs_res = client.get(f"/api/v1/admin/codes/{code_id}/devices", headers=ADMIN_HEADERS)
    assert devs_res.status_code == 200
    device_id = devs_res.json()["data"]["devices"][0]["id"]

    # 5. 上报播放心跳（狂飙 第1集）
    hb_res = client.post(
        "/api/v1/activation/playback-heartbeat",
        headers=dev_headers,
        json={
            "vod_id": "384692",
            "vod_name": "狂飙",
            "vod_pic": "https://example.com/cover.jpg",
            "ep_name": "第1集",
            "site": "www_ncat21_com",
            "position": 120.0,
            "duration": 2400.0,
            "progress": 5,
            "is_playing": True,
        },
    )
    assert hb_res.status_code == 200
    assert hb_res.json()["ok"] is True

    # 6. 验证激活码状态更新为「使用中（正在观看）」
    codes_res2 = client.get("/api/v1/admin/codes", headers=ADMIN_HEADERS)
    c_item2 = next(c for c in codes_res2.json()["data"]["codes"] if c["id"] == code_id)
    assert c_item2["is_online"] is True
    assert c_item2["is_playing"] is True
    assert "狂飙" in c_item2["current_playback"]
    assert "第1集" in c_item2["current_playback"]

    # 7. 进度更新（仍在观看狂飙，进度变成 45%）
    hb_res2 = client.post(
        "/api/v1/activation/playback-heartbeat",
        headers=dev_headers,
        json={
            "vod_id": "384692",
            "vod_name": "狂飙",
            "vod_pic": "https://example.com/cover.jpg",
            "ep_name": "第1集",
            "site": "www_ncat21_com",
            "position": 1080.0,
            "duration": 2400.0,
            "progress": 45,
            "is_playing": True,
        },
    )
    assert hb_res2.status_code == 200

    # 8. 查询设备观看历史记录
    hist_res = client.get(f"/api/v1/admin/devices/{device_id}/history", headers=ADMIN_HEADERS)
    assert hist_res.status_code == 200
    hist_data = hist_res.json()["data"]
    assert hist_data["device_id"] == device_id
    assert hist_data["total"] == 1  # 同一影片只保留一条最新进度记录
    rec = hist_data["records"][0]
    assert rec["vod_name"] == "狂飙"
    assert rec["ep_name"] == "第1集"
    assert rec["progress_percent"] == 45
    assert rec["is_playing"] is True

    # 9. 观看第二部电影（流浪地球）
    client.post(
        "/api/v1/activation/playback-heartbeat",
        headers=dev_headers,
        json={
            "vod_id": "1002",
            "vod_name": "流浪地球",
            "vod_pic": "https://example.com/wandering.jpg",
            "ep_name": "正片",
            "site": "www_ncat21_com",
            "position": 500.0,
            "duration": 7200.0,
            "progress": 7,
            "is_playing": True,
        },
    )

    hist_res2 = client.get(f"/api/v1/admin/devices/{device_id}/history", headers=ADMIN_HEADERS)
    assert hist_res2.json()["data"]["total"] == 2
    top_rec = hist_res2.json()["data"]["records"][0]
    assert top_rec["vod_name"] == "流浪地球"
