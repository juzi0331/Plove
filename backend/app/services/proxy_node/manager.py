"""集中式代理节点池与绑定管理服务。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Optional
import urllib.parse
import uuid

import httpx

from app.core.logging import get_logger
from app.services.proxy_node.engine import xray_engine
from app.services.proxy_node.vless import generate_xray_config, parse_vless_url

logger = get_logger("proxy_node_manager")


def _get_proxy_config_path() -> Path:
    """自动探测 proxy_config.json 的落盘位置。"""
    if env_p := os.environ.get("PROXY_CONFIG_PATH"):
        return Path(env_p)
    project_root = Path(__file__).resolve().parents[4]
    candidate = project_root / "crawler" / "service" / "proxy_config.json"
    if candidate.parent.is_dir():
        return candidate
    cwd_candidate = Path.cwd() / "crawler" / "service" / "proxy_config.json"
    if cwd_candidate.parent.is_dir():
        return cwd_candidate
    fallback = project_root / "backend" / "data" / "proxy_config.json"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback


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

        try:
            if xray_engine.find_binary():
                xray_engine.start_engine(self._nodes)
        except Exception as exc:
            logger.warning("自动启动 Xray 引擎异常: %s", exc)

        return node

    def delete_node(self, node_id: str) -> bool:
        orig = len(self._nodes)
        self._nodes = [n for n in self._nodes if n.get("id") != node_id]
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
