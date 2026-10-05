"""VLESS 节点协议解析与 Xray 客户端配置生成器。"""

from __future__ import annotations

from typing import Any
import urllib.parse


def parse_vless_url(vless_url: str) -> dict[str, Any]:
    """解析标准 vless:// 节点连接串。"""
    url_str = (vless_url or "").strip()
    if not url_str.startswith("vless://"):
        raise ValueError("无效的 VLESS 链接，必须以 vless:// 开头")

    rest = url_str[len("vless://") :]

    name = "VLESS 节点"
    if "#" in rest:
        rest, raw_name = rest.split("#", 1)
        name = urllib.parse.unquote(raw_name).strip() or name

    query_str = ""
    if "?" in rest:
        rest, query_str = rest.split("?", 1)

    if "@" not in rest:
        raise ValueError("VLESS 链接格式错误，缺少 '@' 分隔符")

    uuid_str, host_port = rest.split("@", 1)
    uuid_str = uuid_str.strip()

    if host_port.startswith("[") and "]:" in host_port:
        server = host_port[1 : host_port.index("]:")]
        port_str = host_port[host_port.index("]:") + 2 :]
    elif ":" in host_port:
        server, port_str = host_port.split(":", 1)
    else:
        server = host_port
        port_str = "443"

    try:
        port = int(port_str.strip())
    except ValueError:
        port = 443

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
        "uuid": uuid_str,
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


def parse_trojan_url(trojan_url: str) -> dict[str, Any]:
    """解析标准 trojan:// 节点连接串。"""
    url_str = (trojan_url or "").strip()
    if not url_str.startswith("trojan://"):
        raise ValueError("无效的 Trojan 链接，必须以 trojan:// 开头")

    rest = url_str[len("trojan://") :]

    name = "Trojan 节点"
    if "#" in rest:
        rest, raw_name = rest.split("#", 1)
        name = urllib.parse.unquote(raw_name).strip() or name

    query_str = ""
    if "?" in rest:
        rest, query_str = rest.split("?", 1)

    if "@" not in rest:
        raise ValueError("Trojan 链接格式错误，缺少 '@' 分隔符")

    password, host_port = rest.split("@", 1)
    password = urllib.parse.unquote(password.strip())

    if host_port.startswith("[") and "]:" in host_port:
        server = host_port[1 : host_port.index("]:")]
        port_str = host_port[host_port.index("]:") + 2 :]
    elif ":" in host_port:
        server, port_str = host_port.split(":", 1)
    else:
        server = host_port
        port_str = "443"

    try:
        port = int(port_str.strip())
    except ValueError:
        port = 443

    params = {}
    if query_str:
        for k, v in urllib.parse.parse_qs(query_str).items():
            params[k] = v[0] if v else ""

    network_type = params.get("type", "tcp").lower()
    security = params.get("security", "tls").lower()
    sni = params.get("sni") or params.get("peer") or params.get("serverName") or server
    fp = params.get("fp", "chrome")
    pbk = params.get("pbk", "")
    sid = params.get("sid", "")
    spx = params.get("spx", "")
    path = params.get("path", "")
    host = params.get("host", "")
    service_name = params.get("serviceName", "")
    allow_insecure = params.get("allowInsecure", "0").lower() in ("1", "true", "yes")

    return {
        "raw_url": trojan_url,
        "name": name,
        "password": password,
        "server": server,
        "port": port,
        "type": network_type,
        "security": security,
        "sni": sni,
        "fp": fp,
        "pbk": pbk,
        "sid": sid,
        "spx": spx,
        "path": path,
        "host": host,
        "service_name": service_name,
        "allow_insecure": allow_insecure,
    }


def generate_xray_config(
    node_data: dict[str, Any] | str,
    http_port: int = 10809,
    socks_port: int = 10808,
    listen_ip: str = "127.0.0.1",
) -> dict[str, Any]:
    """生成标准 Xray-core config.json (支持 VLESS 和 Trojan)。"""
    is_trojan = False
    if isinstance(node_data, str):
        if node_data.strip().startswith("trojan://"):
            node_data = parse_trojan_url(node_data)
            is_trojan = True
        else:
            node_data = parse_vless_url(node_data)
    elif node_data.get("protocol") == "trojan" or "password" in node_data:
        is_trojan = True

    server = node_data.get("server", "")
    port = int(node_data.get("port", 443))
    network = node_data.get("type", "tcp")
    security = node_data.get("security", "tls" if is_trojan else "none")
    sni = node_data.get("sni") or server
    fp = node_data.get("fp", "chrome")
    pbk = node_data.get("pbk", "")
    sid = node_data.get("sid", "")
    spx = node_data.get("spx", "")
    path = node_data.get("path", "")
    host = node_data.get("host", "")
    service_name = node_data.get("service_name", "")

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
            "allowInsecure": bool(node_data.get("allow_insecure", False)),
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
        if params_header_type := node_data.get("headerType"):
            stream_settings["tcpSettings"] = {"header": {"type": params_header_type}}

    if is_trojan:
        outbound = {
            "tag": "proxy",
            "protocol": "trojan",
            "settings": {
                "servers": [
                    {
                        "address": server,
                        "port": port,
                        "password": node_data.get("password", ""),
                    }
                ]
            },
            "streamSettings": stream_settings,
        }
    else:
        user_obj: dict[str, Any] = {
            "id": node_data.get("uuid", ""),
            "encryption": "none",
        }
        if flow := node_data.get("flow"):
            user_obj["flow"] = flow
        outbound = {
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
        }

    return {
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
            outbound,
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


def generate_unified_xray_config(
    nodes: list[dict[str, Any]],
    listen_ip: str = "127.0.0.1",
) -> dict[str, Any]:
    """为节点池中所有 VLESS 与 Trojan 节点生成多端口并发代理的统一 Xray config.json。"""
    managed_nodes = [
        n for n in nodes
        if n.get("protocol") in ("vless", "trojan") and n.get("raw_url")
    ]
    inbounds = []
    outbounds = []
    rules = []

    for idx, node in enumerate(managed_nodes):
        node_id = str(node.get("id") or f"node_{idx}")
        local_port = int(node.get("local_port") or (10809 + idx))
        in_tag = f"http-in-{node_id}"
        out_tag = f"proxy-{node_id}"

        inbounds.append({
            "tag": in_tag,
            "port": local_port,
            "listen": listen_ip,
            "protocol": "http",
            "settings": {"timeout": 300},
        })

        protocol = node.get("protocol")
        raw_url = node.get("raw_url", "")
        try:
            if protocol == "trojan":
                parsed = parse_trojan_url(raw_url)
            else:
                parsed = parse_vless_url(raw_url)
        except Exception:
            continue

        stream_settings: dict[str, Any] = {
            "network": parsed.get("type", "tcp"),
            "security": parsed.get("security", "none"),
        }
        sec = parsed.get("security", "none")
        if sec == "reality":
            stream_settings["realitySettings"] = {
                "show": False,
                "fingerprint": parsed.get("fp", "chrome") or "chrome",
                "serverName": parsed.get("sni") or parsed.get("server", ""),
                "publicKey": parsed.get("pbk", ""),
                "shortId": parsed.get("sid", ""),
                "spiderX": parsed.get("spx", "") or "/",
            }
        elif sec == "tls":
            stream_settings["tlsSettings"] = {
                "serverName": parsed.get("sni") or parsed.get("server", ""),
                "fingerprint": parsed.get("fp", "chrome") or "chrome",
                "allowInsecure": bool(parsed.get("allow_insecure", False)),
            }

        net = parsed.get("type", "tcp")
        if net == "ws":
            ws_obj: dict[str, Any] = {}
            if parsed.get("path"):
                ws_obj["path"] = parsed.get("path")
            if parsed.get("host"):
                ws_obj["headers"] = {"Host": parsed.get("host")}
            stream_settings["wsSettings"] = ws_obj
        elif net == "grpc":
            grpc_obj: dict[str, Any] = {}
            if parsed.get("service_name"):
                grpc_obj["serviceName"] = parsed.get("service_name")
            stream_settings["grpcSettings"] = grpc_obj

        if protocol == "trojan":
            outbounds.append({
                "tag": out_tag,
                "protocol": "trojan",
                "settings": {
                    "servers": [
                        {
                            "address": parsed.get("server", ""),
                            "port": int(parsed.get("port", 443)),
                            "password": parsed.get("password", ""),
                        }
                    ]
                },
                "streamSettings": stream_settings,
            })
        else:
            user_obj = {
                "id": parsed.get("uuid", ""),
                "encryption": "none",
            }
            if parsed.get("flow"):
                user_obj["flow"] = parsed.get("flow")

            outbounds.append({
                "tag": out_tag,
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": parsed.get("server", ""),
                            "port": int(parsed.get("port", 443)),
                            "users": [user_obj],
                        }
                    ]
                },
                "streamSettings": stream_settings,
            })

        rules.append({
            "type": "field",
            "inboundTag": [in_tag],
            "outboundTag": out_tag,
        })

    if not inbounds:
        inbounds.append({
            "tag": "http-in-default",
            "port": 10809,
            "listen": listen_ip,
            "protocol": "http",
            "settings": {"timeout": 300},
        })
        rules.append({
            "type": "field",
            "inboundTag": ["http-in-default"],
            "outboundTag": "direct",
        })

    outbounds.append({"tag": "direct", "protocol": "freedom", "settings": {}})
    outbounds.append({"tag": "block", "protocol": "blackhole", "settings": {}})

    return {
        "log": {"loglevel": "warning"},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "AsIs",
            "rules": rules,
        },
    }
