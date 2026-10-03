"""VLESS 节点解析器与 Xray 客户端配置生成器。

支持将标准 vless:// 节点连接串自动解析为结构化参数，
并一键生成标准 Xray-core client config.json 配置，提供本地 HTTP (10809) 与 SOCKS5 (10808) 代理端口。
"""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Optional


def parse_vless_url(vless_url: str) -> dict[str, Any]:
    """解析标准 vless:// 节点链接。
    
    格式示例:
    vless://uuid@server:port?type=tcp&security=reality&pbk=xxx&fp=chrome&sni=xxx&sid=xxx&flow=xtls-rprx-vision#NodeName
    """
    url_str = (vless_url or "").strip()
    if not url_str.startswith("vless://"):
        raise ValueError("无效的 VLESS 链接，必须以 vless:// 开头")

    # 去掉 vless:// 前缀
    rest = url_str[len("vless://"):]
    
    # 提取备注名 (#后面的部分)
    name = "VLESS 节点"
    if "#" in rest:
        rest, raw_name = rest.split("#", 1)
        name = urllib.parse.unquote(raw_name).strip() or name

    # 提取查询参数 (?后面的部分)
    query_str = ""
    if "?" in rest:
        rest, query_str = rest.split("?", 1)

    # 提取 uuid 和 server:port
    if "@" not in rest:
        raise ValueError("VLESS 链接格式错误，缺少 '@' 分隔符")

    uuid, host_port = rest.split("@", 1)
    uuid = uuid.strip()

    # 处理 IPv6 或常规 host:port
    if host_port.startswith("[") and "]:" in host_port:
        server = host_port[1:host_port.index("]:")]
        port_str = host_port[host_port.index("]:") + 2:]
    elif ":" in host_port:
        server, port_str = host_port.split(":", 1)
    else:
        server = host_port
        port_str = "443"

    try:
        port = int(port_str.strip())
    except ValueError:
        port = 443

    # 解析 query 参数
    params = {}
    if query_str:
        for k, v in urllib.parse.parse_qs(query_str).items():
            params[k] = v[0] if v else ""

    network_type = params.get("type", "tcp").lower()
    security = params.get("security", "none").lower()
    flow = params.get("flow", "")
    sni = params.get("sni") or params.get("serverName") or server
    fp = params.get("fp", "chrome")
    pbk = params.get("pbk", "")
    sid = params.get("sid", "")
    spx = params.get("spx", "")
    path = params.get("path", "")
    host = params.get("host", "")
    service_name = params.get("serviceName", "")

    return {
        "raw_url": vless_url,
        "name": name,
        "uuid": uuid,
        "server": server,
        "port": port,
        "type": network_type,
        "security": security,
        "flow": flow,
        "sni": sni,
        "fp": fp,
        "pbk": pbk,
        "sid": sid,
        "spx": spx,
        "path": path,
        "host": host,
        "service_name": service_name,
    }


def generate_xray_config(
    vless_data: dict[str, Any] | str,
    http_port: int = 10809,
    socks_port: int = 10808,
    listen_ip: str = "127.0.0.1",
) -> dict[str, Any]:
    """根据解析后的 VLESS 数据生成标准的 Xray-core 配置文件字典。"""
    if isinstance(vless_data, str):
        vless_data = parse_vless_url(vless_data)

    uuid = vless_data.get("uuid", "")
    server = vless_data.get("server", "")
    port = int(vless_data.get("port", 443))
    network = vless_data.get("type", "tcp")
    security = vless_data.get("security", "none")
    flow = vless_data.get("flow", "")
    sni = vless_data.get("sni") or server
    fp = vless_data.get("fp", "chrome")
    pbk = vless_data.get("pbk", "")
    sid = vless_data.get("sid", "")
    spx = vless_data.get("spx", "")
    path = vless_data.get("path", "")
    host = vless_data.get("host", "")
    service_name = vless_data.get("service_name", "")

    # 用户信息
    user_obj: dict[str, Any] = {
        "id": uuid,
        "encryption": "none",
    }
    if flow:
        user_obj["flow"] = flow

    # 传输层设置
    stream_settings: dict[str, Any] = {
        "network": network,
        "security": security,
    }

    if security == "reality":
        stream_settings["realitySettings"] = {
            "show": False,
            "fingerprint": fp or "chrome",
            "serverName": sni,
            "publicKey": pbk,
            "shortId": sid,
            "spiderX": spx or "/",
        }
    elif security == "tls":
        stream_settings["tlsSettings"] = {
            "serverName": sni,
            "fingerprint": fp or "chrome",
            "allowInsecure": False,
        }

    if network == "ws":
        ws_obj: dict[str, Any] = {}
        if path:
            ws_obj["path"] = path
        if host:
            ws_obj["headers"] = {"Host": host}
        stream_settings["wsSettings"] = ws_obj
    elif network == "grpc":
        grpc_obj: dict[str, Any] = {}
        if service_name:
            grpc_obj["serviceName"] = service_name
        stream_settings["grpcSettings"] = grpc_obj
    elif network == "tcp":
        if params_header_type := vless_data.get("headerType"):
            stream_settings["tcpSettings"] = {
                "header": {"type": params_header_type}
            }

    config = {
        "log": {
            "loglevel": "warning",
        },
        "inbounds": [
            {
                "tag": "http-in",
                "port": http_port,
                "listen": listen_ip,
                "protocol": "http",
                "settings": {
                    "timeout": 300,
                },
            },
            {
                "tag": "socks-in",
                "port": socks_port,
                "listen": listen_ip,
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": True,
                },
            },
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": server,
                            "port": port,
                            "users": [user_obj],
                        }
                    ]
                },
                "streamSettings": stream_settings,
            },
            {
                "tag": "direct",
                "protocol": "freedom",
                "settings": {},
            },
            {
                "tag": "block",
                "protocol": "blackhole",
                "settings": {},
            },
        ],
    }

    return config
