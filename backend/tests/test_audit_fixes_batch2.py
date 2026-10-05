"""回归与功能验证测试集：AUD-05, AUD-06, AUD-20, AUD-21, AUD-22。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from app.core.errors import AppError
from app.models.activation import ActivationCode
from app.models.device import Device
from app.models.playback import PlaybackRecord
from app.modules.experience.application.publish_release import publish_experience_release
from app.modules.experience.infrastructure.sqlalchemy_experience_repository import (
    SqlAlchemyExperienceRepository,
)
from app.schemas.playback import PlaybackHeartbeatRequest
from app.services.playback_service import record_playback_heartbeat
from app.services.proxy_node.manager import ProxyNodeManager
from app.services.proxy_node.vless import (
    generate_unified_xray_config,
    parse_trojan_url,
    parse_vless_url,
)


def test_parse_trojan_url_valid():
    """AUD-05: 测试 Trojan 协议解析。"""
    raw = "trojan://secret-pwd@node.example.com:8443?security=tls&sni=sni.example.com&type=ws&path=%2Ftrojan#TrojanNode"
    parsed = parse_trojan_url(raw)
    assert parsed["name"] == "TrojanNode"
    assert parsed["password"] == "secret-pwd"
    assert parsed["server"] == "node.example.com"
    assert parsed["port"] == 8443
    assert parsed["type"] == "ws"
    assert parsed["security"] == "tls"
    assert parsed["sni"] == "sni.example.com"
    assert parsed["path"] == "/trojan"


def test_parse_trojan_url_invalid():
    """AUD-05: 测试非法 Trojan 协议报错。"""
    with pytest.raises(ValueError, match="必须以 trojan:// 开头"):
        parse_trojan_url("vless://abc@host:443")

    with pytest.raises(ValueError, match="缺少 '@' 分隔符"):
        parse_trojan_url("trojan://host:443")


def test_generate_unified_xray_config_with_trojan():
    """AUD-05: 测试统一 Xray 配置包含 Trojan 与 VLESS 出站。"""
    nodes = [
        {
            "id": "vless_1",
            "protocol": "vless",
            "local_port": 10809,
            "raw_url": "vless://11111111-2222-3333-4444-555555555555@vless.example.com:443?security=tls#VLESS1",
        },
        {
            "id": "trojan_1",
            "protocol": "trojan",
            "local_port": 10810,
            "raw_url": "trojan://password123@trojan.example.com:443?security=tls&sni=sni.trojan.com#Trojan1",
        },
    ]

    cfg = generate_unified_xray_config(nodes)
    inbounds = cfg["inbounds"]
    outbounds = cfg["outbounds"]
    rules = cfg["routing"]["rules"]

    assert len(inbounds) == 2
    assert inbounds[0]["port"] == 10809
    assert inbounds[1]["port"] == 10810

    # 包含 vless 和 trojan 出站，以及 direct 和 block
    outbound_protocols = [o["protocol"] for o in outbounds]
    assert "vless" in outbound_protocols
    assert "trojan" in outbound_protocols

    # 验证 trojan outbound 结构
    trojan_out = next(o for o in outbounds if o["tag"] == "proxy-trojan_1")
    assert trojan_out["protocol"] == "trojan"
    assert trojan_out["settings"]["servers"][0]["password"] == "password123"
    assert trojan_out["settings"]["servers"][0]["address"] == "trojan.example.com"
    assert trojan_out["streamSettings"]["security"] == "tls"
    assert trojan_out["streamSettings"]["tlsSettings"]["serverName"] == "sni.trojan.com"

    # 验证路由分流规则绑定
    rule_tags = [(r["inboundTag"][0], r["outboundTag"]) for r in rules]
    assert ("http-in-vless_1", "proxy-vless_1") in rule_tags
    assert ("http-in-trojan_1", "proxy-trojan_1") in rule_tags


def test_proxy_node_manager_add_and_reimport_http_socks(tmp_path):
    """AUD-05 & AUD-06: 测试 Trojan 导入以及 HTTP/SOCKS 节点重复导入不被改坏。"""
    config_file = tmp_path / "proxy_config.json"
    mgr = ProxyNodeManager(config_path=config_file)

    with patch("app.services.proxy_node.engine.xray_engine.start_engine"):
        # 1. 导入 Trojan 节点
        trojan_url = "trojan://mypassword@trojan.node:443?sni=trojan.node#MyTrojan"
        node_trojan = mgr.add_node(trojan_url, local_port=10809)
        assert node_trojan["protocol"] == "trojan"
        assert node_trojan["proxy_url"] == f"http://127.0.0.1:{node_trojan['local_port']}"

        # 2. 导入 HTTP 节点
        http_url = "http://upstream.proxy.com:8080"
        node_http = mgr.add_node(http_url, custom_name="Remote HTTP")
        assert node_http["protocol"] == "http"
        assert node_http["proxy_url"] == http_url

        # 3. 再次重复导入相同的 HTTP 节点 (AUD-06)
        node_http_reimport = mgr.add_node(http_url, custom_name="Remote HTTP Updated")
        assert node_http_reimport["id"] == node_http["id"]
        # 关键验证：不可被篡改为 127.0.0.1:{local_port}
        assert node_http_reimport["proxy_url"] == http_url
        assert node_http_reimport["name"] == "Remote HTTP Updated"

        # 4. 尝试导入不受支持的协议链接应被拒绝，不可误识别为 http
        with pytest.raises(ValueError, match="不支持的代理协议或链接格式"):
            mgr.add_node("unknown_proto://some_server:1234")


def test_playback_records_isolated_by_site_key(db_session):
    """AUD-20: 验证跨站观看历史按 site_key 隔离不互相覆盖。"""
    # 准备基础数据
    code = ActivationCode(code="SITE_TEST_CODE_01", duration_hours=24 * 30)
    db_session.add(code)
    db_session.flush()

    dev = Device(token="DEV_TOKEN_01", activation_id=code.id)
    db_session.add(dev)
    db_session.flush()

    # 1. 在 site_a 观看影片 100
    req_a = PlaybackHeartbeatRequest(
        vod_id="100",
        vod_name="片目 A (Site A)",
        site="site_a",
        ep_name="第01集",
        position=120.0,
        duration=1200.0,
        progress=10,
        is_playing=True,
    )
    res_a = record_playback_heartbeat(db_session, dev, req_a)
    assert res_a.ok is True

    # 2. 在 site_b 观看影片 100（同 vod_id，不同 site）
    req_b = PlaybackHeartbeatRequest(
        vod_id="100",
        vod_name="片目 B (Site B)",
        site="site_b",
        ep_name="第02集",
        position=300.0,
        duration=1500.0,
        progress=20,
        is_playing=True,
    )
    res_b = record_playback_heartbeat(db_session, dev, req_b)
    assert res_b.ok is True

    # 验证两条记录均保留
    records = db_session.query(PlaybackRecord).filter_by(device_id=dev.id, vod_id="100").all()
    assert len(records) == 2
    sites = {r.site_key: r.vod_name for r in records}
    assert sites["site_a"] == "片目 A (Site A)"
    assert sites["site_b"] == "片目 B (Site B)"

    # 3. 再次在 site_a 播放影片 100，应更新 site_a 的旧记录
    req_a2 = PlaybackHeartbeatRequest(
        vod_id="100",
        vod_name="片目 A (Site A)",
        site="site_a",
        ep_name="第01集",
        position=600.0,
        duration=1200.0,
        progress=50,
        is_playing=True,
    )
    record_playback_heartbeat(db_session, dev, req_a2)
    records_after = db_session.query(PlaybackRecord).filter_by(device_id=dev.id, vod_id="100").all()
    assert len(records_after) == 2
    rec_a = next(r for r in records_after if r.site_key == "site_a")
    assert rec_a.position == 600.0
    assert rec_a.progress_percent == 50


def test_experience_draft_cas_concurrency(db_session):
    """AUD-21: 验证草稿版本并发保存冲突保护。"""
    repo = SqlAlchemyExperienceRepository(db_session)
    draft = repo.get_or_create_draft("default")
    initial_rev = draft.revision

    # 正常提交更新
    repo.save_draft(
        draft_id="default",
        current_revision=initial_rev,
        brand_json=draft.brand_json,
        theme_json=draft.theme_json,
        navigation_json=draft.navigation_json,
        pages_json=draft.pages_json,
        player_defaults_json=draft.player_defaults_json,
        updated_by="editor_A",
    )
    assert draft.revision == initial_rev + 1

    # 持有陈旧 revision 的编辑者尝试保存，必须抛出 AppError
    with pytest.raises(AppError, match="已被其他人修改|并发保存冲突"):
        repo.save_draft(
            draft_id="default",
            current_revision=initial_rev,  # 旧版本
            brand_json=draft.brand_json,
            theme_json=draft.theme_json,
            navigation_json=draft.navigation_json,
            pages_json=draft.pages_json,
            player_defaults_json=draft.player_defaults_json,
            updated_by="editor_B",
        )


def test_experience_release_unique_id_in_same_second(db_session):
    """AUD-22: 验证同一秒内多次发布不会产生相同的 release_id。"""
    repo = SqlAlchemyExperienceRepository(db_session)
    draft = repo.get_or_create_draft("default")

    # 同一时刻快速连续发布两次
    res1 = publish_experience_release(db_session, draft_id="default", note="Release 1")
    res2 = publish_experience_release(db_session, draft_id="default", note="Release 2")

    assert res1.release_id != res2.release_id
    assert res2.revision > res1.revision
