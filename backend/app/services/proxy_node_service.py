"""集中式代理节点池与 VLESS 解析服务。

支持：
1. VLESS 节点解析（URL Scheme 提取 UUID、远端服务器、端口、Reality/TLS、gRPC/WS等参数）；
2. 标准 Xray-core client config.json 导出，方便在宝塔面板或 NAS 宿主机运行 Xray；
3. 多节点管理（VLESS / HTTP / SOCKS5）与连通性测速；
4. 采集器与代理节点一对一/多对一绑定。
"""

from __future__ import annotations

import atexit
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
from typing import Any, Optional
import urllib.parse
import uuid
import zipfile

import httpx

from app.core.logging import get_logger

logger = get_logger("proxy_node_service")


def _get_proxy_config_path() -> Path:
    """自动探测 proxy_config.json 的落盘位置。"""
    # 1. 环境变量优先
    if env_p := os.environ.get("PROXY_CONFIG_PATH"):
        return Path(env_p)
    # 2. 相对于当前源码结构: Plove1.0/crawler/service/proxy_config.json
    project_root = Path(__file__).resolve().parents[3]
    candidate = project_root / "crawler" / "service" / "proxy_config.json"
    if candidate.parent.is_dir():
        return candidate
    # 3. 备选：当前工作目录
    cwd_candidate = Path.cwd() / "crawler" / "service" / "proxy_config.json"
    if cwd_candidate.parent.is_dir():
        return cwd_candidate
    # 4. 后端内置目录
    fallback = project_root / "backend" / "data" / "proxy_config.json"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback


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


def generate_xray_config(
    vless_data: dict[str, Any] | str,
    http_port: int = 10809,
    socks_port: int = 10808,
    listen_ip: str = "0.0.0.0",
) -> dict[str, Any]:
    """生成标准 Xray-core config.json。"""
    if isinstance(vless_data, str):
        vless_data = parse_vless_url(vless_data)

    uuid_str = vless_data.get("uuid", "")
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

    user_obj: dict[str, Any] = {
        "id": uuid_str,
        "encryption": "none",
    }
    if flow:
        user_obj["flow"] = flow

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
            stream_settings["tcpSettings"] = {"header": {"type": params_header_type}}

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


def generate_unified_xray_config(
    nodes: list[dict[str, Any]],
    listen_ip: str = "0.0.0.0",
) -> dict[str, Any]:
    """为节点池中所有 VLESS 节点生成多端口并发代理的统一 Xray config.json。"""
    vless_nodes = [n for n in nodes if n.get("protocol") == "vless" and n.get("raw_url")]
    inbounds = []
    outbounds = []
    rules = []

    for idx, node in enumerate(vless_nodes):
        node_id = str(node.get("id") or f"node_{idx}")
        local_port = int(node.get("local_port") or (10809 + idx))
        in_tag = f"http-in-{node_id}"
        out_tag = f"proxy-{node_id}"

        # 1. 本地入站 HTTP 端口
        inbounds.append({
            "tag": in_tag,
            "port": local_port,
            "listen": listen_ip,
            "protocol": "http",
            "settings": {"timeout": 300},
        })

        # 2. 远端出站 VLESS 节点
        try:
            parsed = parse_vless_url(node.get("raw_url", ""))
        except Exception:
            continue

        user_obj = {
            "id": parsed.get("uuid", ""),
            "encryption": "none",
        }
        if parsed.get("flow"):
            user_obj["flow"] = parsed.get("flow")

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
                "allowInsecure": False,
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

        # 3. 严格分流：每个端口映射到特定 VLESS 节点
        rules.append({
            "type": "field",
            "inboundTag": [in_tag],
            "outboundTag": out_tag,
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


class XrayEngineManager:
    """Xray-core 内置守护进程与一键安装管理器。"""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._last_error: Optional[str] = None
        self._managed_ports: list[int] = []
        self._managed_nodes: list[str] = []
        atexit.register(self.stop_engine)

    def get_bin_dir(self) -> Path:
        base_dir = Path(__file__).resolve().parents[2]
        bin_dir = base_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        return bin_dir

    def find_binary(self) -> Optional[Path]:
        exe_name = "xray.exe" if os.name == "nt" else "xray"
        candidates = [
            self.get_bin_dir() / exe_name,
            Path(__file__).resolve().parents[3] / "bin" / exe_name,
            Path.cwd() / "bin" / exe_name,
            Path.cwd() / "backend" / "bin" / exe_name,
            Path.cwd() / "crawler" / "bin" / exe_name,
            Path("/usr/local/bin/xray"),
            Path("/usr/bin/xray"),
        ]
        for c in candidates:
            if c.is_file():
                return c
        which_p = shutil.which(exe_name) or shutil.which("xray")
        if which_p:
            return Path(which_p)
        return None

    def install_binary_sync(self) -> dict[str, Any]:
        """同步下载并安装 Xray-core 独立内核（自动适配 Windows / Linux / macOS / ARM64）。"""
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "windows":
            asset_name = "Xray-windows-64.zip"
            exe_name = "xray.exe"
        elif system == "linux":
            exe_name = "xray"
            if "arm" in machine or "aarch64" in machine:
                asset_name = "Xray-linux-arm64-v8a.zip"
            else:
                asset_name = "Xray-linux-64.zip"
        elif system == "darwin":
            exe_name = "xray"
            if "arm" in machine:
                asset_name = "Xray-macos-arm64-v8a.zip"
            else:
                asset_name = "Xray-macos-64.zip"
        else:
            raise RuntimeError(f"不支持的系统平台: {system} {machine}")

        tag = "v24.9.30"
        urls = [
            f"https://ghfast.top/https://github.com/XTLS/Xray-core/releases/download/{tag}/{asset_name}",
            f"https://ghproxy.net/https://github.com/XTLS/Xray-core/releases/download/{tag}/{asset_name}",
            f"https://github.moeyy.xyz/https://github.com/XTLS/Xray-core/releases/download/{tag}/{asset_name}",
            f"https://github.com/XTLS/Xray-core/releases/download/{tag}/{asset_name}",
        ]

        bin_dir = self.get_bin_dir()
        target_exe = bin_dir / exe_name

        downloaded = False
        last_exc = None
        for url in urls:
            try:
                logger.info("正在从镜像源下载 Xray-core 内核: %s", url)
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    if resp.status == 200:
                        content = resp.read()
                        if len(content) > 1024 * 1024:
                            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                                for member in zf.namelist():
                                    if member in (exe_name, "xray", "xray.exe", "geoip.dat", "geosite.dat", "LICENSE", "README.md"):
                                        zf.extract(member, bin_dir)
                            if os.name != "nt":
                                try:
                                    target_exe.chmod(0o755)
                                except Exception:
                                    pass
                            downloaded = True
                            logger.info("Xray-core 内核安装就绪: %s", target_exe)
                            break
            except Exception as exc:
                last_exc = exc
                logger.warning("镜像源下载尝试失败 (%s): %s", url, exc)

        if not downloaded:
            raise RuntimeError(f"下载 Xray 内核失败，所有镜像源均超时或失败: {last_exc}")

        return {
            "success": True,
            "bin_path": str(target_exe),
            "version": tag,
        }

    async def install_binary(self) -> dict[str, Any]:
        """全自动下载并安装 Xray-core 独立内核。"""
        import asyncio
        return await asyncio.to_thread(self.install_binary_sync)

    def start_engine(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """为所有 VLESS 节点启动统一的 Xray 代理进程。"""
        bin_p = self.find_binary()
        if not bin_p:
            return {"running": False, "error": "未安装 Xray 核心引擎"}

        vless_nodes = [n for n in nodes if n.get("protocol") == "vless" and n.get("raw_url")]
        if not vless_nodes:
            self.stop_engine()
            return {"running": False, "message": "暂无 VLESS 节点需要中转"}

        self.stop_engine()

        cfg = generate_unified_xray_config(vless_nodes)
        config_path = self.get_bin_dir().parent / "data" / "xray_unified.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

        try:
            if os.name != "nt":
                try:
                    bin_p.chmod(bin_p.stat().st_mode | 0o755)
                except Exception:
                    pass

            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

            proc = subprocess.Popen(
                [str(bin_p), "run", "-c", str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
            )
            self._proc = proc
            time.sleep(0.6)
            if proc.poll() is not None:
                err_out = ""
                try:
                    _, err_bytes = proc.communicate(timeout=0.5)
                    err_out = (err_bytes or "").strip()
                except Exception:
                    pass
                self._proc = None
                self._last_error = f"Xray 启动后异常退出: {err_out}" if err_out else "Xray 启动后异常退出，请检查节点配置"
                return {"running": False, "error": self._last_error}

            self._last_error = None
            self._managed_ports = [int(n.get("local_port", 10809)) for n in vless_nodes]
            self._managed_nodes = [str(n.get("name", "")) for n in vless_nodes]

            logger.info("Xray 引擎启动成功 (PID %s), 监听端口: %s", proc.pid, self._managed_ports)
            return {
                "running": True,
                "pid": proc.pid,
                "managed_ports": self._managed_ports,
                "managed_nodes": self._managed_nodes,
            }
        except Exception as exc:
            self._last_error = str(exc)
            logger.error("启动 Xray 引擎异常: %s", exc)
            return {"running": False, "error": str(exc)}

    def stop_engine(self) -> dict[str, Any]:
        """停止 Xray 守护进程。"""
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._managed_ports = []
        self._managed_nodes = []
        return {"running": False}

    def get_status(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """获取引擎安装与运行状态。"""
        bin_p = self.find_binary()
        is_running = bool(self._proc and self._proc.poll() is None)
        vless_nodes = [n for n in nodes if n.get("protocol") == "vless" and n.get("raw_url")]
        ports = [int(n.get("local_port", 10809)) for n in vless_nodes]
        names = [str(n.get("name", "")) for n in vless_nodes]

        return {
            "installed": bin_p is not None,
            "running": is_running,
            "pid": self._proc.pid if is_running else None,
            "version": "v24.9.30" if bin_p else None,
            "bin_path": str(bin_p) if bin_p else None,
            "managed_ports": ports if is_running else [],
            "managed_nodes": names if is_running else [],
            "error": self._last_error,
        }


xray_engine = XrayEngineManager()


class ProxyNodeManager:
    """管理节点池与绑定的单例服务。"""

    def __init__(self) -> None:
        self.config_path = _get_proxy_config_path()
        self._enabled: bool = False
        self._default_proxy_url: str = "http://127.0.0.1:10809"
        self._nodes: list[dict[str, Any]] = []
        self._bindings: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        if self.config_path.is_file():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self._enabled = bool(data.get("enabled", False))
                self._default_proxy_url = str(
                    data.get("default_proxy_url") or data.get("proxy_url") or "http://127.0.0.1:10809"
                ).strip()
                self._nodes = list(data.get("nodes", []))
                self._bindings = dict(data.get("bindings", {}))
            except Exception as exc:
                logger.warning("读取代理节点配置失败: %s", exc)

        if not self._nodes:
            self._nodes.append(
                {
                    "id": "node_default",
                    "name": "本地默认代理 (10809)",
                    "protocol": "http",
                    "proxy_url": self._default_proxy_url or "http://127.0.0.1:10809",
                    "raw_url": self._default_proxy_url or "http://127.0.0.1:10809",
                    "server": "127.0.0.1",
                    "port": 10809,
                    "local_port": 10809,
                }
            )

    def save(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(
                    {
                        "enabled": self._enabled,
                        "default_proxy_url": self._default_proxy_url,
                        "proxy_url": self._default_proxy_url,
                        "nodes": self._nodes,
                        "bindings": self._bindings,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("保存代理配置失败: %s", exc)

    def get_data(self) -> dict[str, Any]:
        self.load()
        valid_node_ids = {n.get("id") for n in self._nodes}
        active_bindings = {
            k: v for k, v in self._bindings.items()
            if v and v not in ("direct", "none", "default") and v in valid_node_ids
        }
        return {
            "enabled": self._enabled,
            "default_proxy_url": self._default_proxy_url,
            "nodes": self._nodes,
            "bindings": active_bindings,
        }

    def get_nodes(self) -> list[dict[str, Any]]:
        self.load()
        return self._nodes

    def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        for n in self._nodes:
            if n.get("id") == node_id:
                return n
        return None

    def add_node(self, raw_input: str, custom_name: str = "", local_port: int = 10809) -> dict[str, Any]:
        text = (raw_input or "").strip()
        if not text:
            raise ValueError("节点连接串不能为空")

        node_id = f"node_{uuid.uuid4().hex[:8]}"

        if text.startswith("vless://"):
            parsed = parse_vless_url(text)
            name = custom_name.strip() or parsed.get("name") or f"VLESS ({parsed.get('server')})"

            # 自动分配合适的本地端口，避免冲突
            used_ports = {int(n.get("local_port", 0)) for n in self._nodes if n.get("protocol") == "vless"}
            alloc_port = local_port
            while alloc_port in used_ports:
                alloc_port += 1
            local_port = alloc_port

            local_http_proxy = f"http://127.0.0.1:{local_port}"
            node = {
                "id": node_id,
                "name": name,
                "protocol": "vless",
                "raw_url": text,
                "proxy_url": local_http_proxy,
                "local_http_proxy": local_http_proxy,
                "local_port": local_port,
                "server": parsed.get("server", ""),
                "port": parsed.get("port", 443),
                "network_type": parsed.get("type", "tcp"),
                "security": parsed.get("security", "none"),
                "sni": parsed.get("sni") or parsed.get("server", ""),
                "parsed_data": parsed,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            # 自动探测核心，未安装则尝试静默一键拉取
            if not xray_engine.find_binary():
                try:
                    xray_engine.install_binary_sync()
                except Exception as exc:
                    logger.warning("尝试自动下载安装 Xray 核心失败: %s", exc)
        else:
            proxy_url = text
            if not proxy_url.startswith(("http://", "https://", "socks5://", "socks://")):
                proxy_url = f"http://{proxy_url}"
            name = custom_name.strip() or f"代理节点 ({proxy_url.replace('http://', '')})"
            proto = "socks5" if proxy_url.startswith("socks") else "http"
            parsed_u = urllib.parse.urlparse(proxy_url)
            node = {
                "id": node_id,
                "name": name,
                "protocol": proto,
                "raw_url": text,
                "proxy_url": proxy_url,
                "local_http_proxy": proxy_url,
                "local_port": parsed_u.port or (10808 if proto == "socks5" else 10809),
                "server": parsed_u.hostname or "127.0.0.1",
                "port": parsed_u.port or 10809,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

        # 查重更新
        for i, item in enumerate(self._nodes):
            if item.get("raw_url") == text:
                node["id"] = item["id"]
                node["local_port"] = item.get("local_port", node["local_port"])
                node["proxy_url"] = f"http://127.0.0.1:{node['local_port']}"
                self._nodes[i] = node
                self.save()
                try:
                    if xray_engine.find_binary():
                        xray_engine.start_engine(self._nodes)
                except Exception:
                    pass
                return node

        self._nodes.append(node)
        self.save()

        # 自动热启动/重启内置引擎
        try:
            if xray_engine.find_binary():
                xray_engine.start_engine(self._nodes)
        except Exception as exc:
            logger.warning("自动启动 Xray 引擎异常: %s", exc)

        return node

    def delete_node(self, node_id: str) -> bool:
        orig = len(self._nodes)
        self._nodes = [n for n in self._nodes if n.get("id") != node_id]
        # 解绑已删除的节点
        for k, v in list(self._bindings.items()):
            if v == node_id:
                self._bindings.pop(k, None)
        self.save()

        try:
            if xray_engine.find_binary():
                xray_engine.start_engine(self._nodes)
        except Exception:
            pass

        return len(self._nodes) < orig

    def bind_site(self, site_key: str, node_id: str) -> dict[str, Any]:
        clean_key = (site_key or "").strip().lower()
        clean_node = (node_id or "").strip()
        if not clean_key:
            raise ValueError("site_key 不能为空")

        if not clean_node or clean_node in ("direct", "none", "default"):
            self._bindings.pop(clean_key, None)
            self.save()
            return {
                "site_key": clean_key,
                "node_id": "direct",
            }

        self._bindings[clean_key] = clean_node
        self.save()
        return {
            "site_key": clean_key,
            "node_id": clean_node,
        }

    def unbind_site(self, site_key: str) -> dict[str, Any]:
        return self.bind_site(site_key, "direct")

    def export_xray(self, node_id: str, http_port: int = 10809, socks_port: int = 10808) -> dict[str, Any]:
        node = self.get_node(node_id)
        if not node:
            raise ValueError(f"未找到节点: {node_id}")
        if node.get("protocol") != "vless":
            raise ValueError("只有 VLESS 协议节点支持导出 Xray 核心配置文件")
        raw = node.get("raw_url", "")
        return generate_xray_config(raw, http_port=http_port, socks_port=socks_port)

    async def test_node_connection(
        self,
        node_id: Optional[str] = None,
        custom_proxy: Optional[str] = None,
        target_url: str = "https://www.google.com/generate_204",
    ) -> dict[str, Any]:
        proxy = custom_proxy
        if node_id:
            node = self.get_node(node_id)
            if node:
                proxy = node.get("proxy_url")
                # 如果是 VLESS 且 Xray 内核已安装但未启动，自动唤醒启动
                if node.get("protocol") == "vless":
                    if not xray_engine.find_binary():
                        try:
                            await xray_engine.install_binary()
                        except Exception:
                            pass
                    if xray_engine.find_binary() and not xray_engine.get_status(self._nodes)["running"]:
                        xray_engine.start_engine(self._nodes)
        if not proxy:
            proxy = self._default_proxy_url

        start = time.monotonic()
        targets = [target_url]
        if "google.com" in target_url:
            targets.append("https://www.cloudflare.com/cdn-cgi/trace")
            targets.append("http://cp.cloudflare.com/generate_204")

        last_exc = None
        for test_target in targets:
            try:
                async with httpx.AsyncClient(proxy=proxy, verify=False, timeout=8.0) as client:
                    resp = await client.get(test_target)
                    duration = round((time.monotonic() - start) * 1000, 1)
                    is_ok = resp.status_code in (200, 204, 301, 302)
                    if is_ok:
                        return {
                            "ok": True,
                            "status_code": resp.status_code,
                            "duration_ms": duration,
                            "proxy_used": proxy or "直连",
                            "message": f"连接正常 (HTTP {resp.status_code}, 延迟 {duration}ms)",
                        }
            except Exception as exc:
                last_exc = exc

        duration = round((time.monotonic() - start) * 1000, 1)
        return {
            "ok": False,
            "status_code": 0,
            "duration_ms": duration,
            "proxy_used": proxy or "直连",
            "message": f"连接失败: {last_exc}",
        }


proxy_node_service = ProxyNodeManager()
