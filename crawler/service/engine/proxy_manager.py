"""代理与节点管理器：支持节点池管理（VLESS / HTTP / SOCKS5）与多采集器独立指派。

功能：
1. 节点池管理：用户可添加多个节点（支持直接粘贴 vless:// 节点或输入 http:// 代理），解析元数据；
2. 采集器绑定控制：可视化指派每个采集器适配器（如 huangguoai_com）绑定到哪个节点，或选择直连；
3. 子进程环境隔离：按采集器 key 独立注入对应的 HTTP_PROXY / HTTPS_PROXY；
4. Xray 配置文件一键导出：方便部署在本地 NAS 宝塔面板时，1秒生成 config.json 启动 Xray-core。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Optional
import uuid
import httpx

from ..core.log import get_logger
from .vless_manager import parse_vless_url, generate_xray_config

logger = get_logger("proxy_manager")


class ProxyManager:
    """集中式代理管理器：管理节点池、采集器指派映射、测试连通性与子进程代理注入。"""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or Path(__file__).resolve().parents[1] / "proxy_config.json"
        self._enabled: bool = False
        self._default_proxy_url: str = "http://127.0.0.1:10809"
        self._nodes: list[dict[str, Any]] = []
        self._bindings: dict[str, str] = {}  # {site_key: node_id 或 "direct" 或 "default"}
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

                # 兼容老版 sites 结构
                if "sites" in data and not self._bindings:
                    for s_key, s_val in data["sites"].items():
                        if isinstance(s_val, dict) and s_val.get("enabled") and s_val.get("proxy_url"):
                            node_id = f"node_legacy_{s_key}"
                            self._nodes.append({
                                "id": node_id,
                                "name": f"老版配置 ({s_key})",
                                "protocol": "http",
                                "proxy_url": s_val["proxy_url"],
                                "raw_url": s_val["proxy_url"],
                            })
                            self._bindings[s_key] = node_id
            except Exception as exc:
                logger.warning("读取代理配置失败: %s", exc)

        # 默认确保至少有一个本地默认节点
        if not self._nodes:
            self._nodes.append({
                "id": "node_default",
                "name": "本地默认代理 (10809)",
                "protocol": "http",
                "proxy_url": self._default_proxy_url or "http://127.0.0.1:10809",
                "raw_url": self._default_proxy_url or "http://127.0.0.1:10809",
                "server": "127.0.0.1",
                "port": 10809,
            })

        self._apply_env()

    def save(self) -> None:
        try:
            self.config_path.write_text(
                json.dumps(
                    {
                        "enabled": self._enabled,
                        "default_proxy_url": self._default_proxy_url,
                        # 兼容字段
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
        self._apply_env()

    def _apply_env(self) -> None:
        """根据全局状态设置或清除主进程环境变量。"""
        if self._enabled and self._default_proxy_url:
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                os.environ[k] = self._default_proxy_url
            logger.info("已启用全局网络代理: %s", self._default_proxy_url)
        else:
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                os.environ.pop(k, None)
            logger.info("已停用全局网络代理 (系统直连)")

    # ------------------------------------------------------------- 基础配置读取
    def get_config(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "default_proxy_url": self._default_proxy_url,
            "proxy_url": self._default_proxy_url,
            "nodes": self._nodes,
            "bindings": self._bindings,
        }

    def set_config(self, enabled: bool, proxy_url: str) -> dict[str, Any]:
        self._enabled = bool(enabled)
        if proxy_url:
            self._default_proxy_url = str(proxy_url).strip()
        self.save()
        return self.get_config()

    # ------------------------------------------------------------- 节点管理
    def get_nodes(self) -> list[dict[str, Any]]:
        return self._nodes

    def get_node_by_id(self, node_id: str) -> Optional[dict[str, Any]]:
        for n in self._nodes:
            if n.get("id") == node_id:
                return n
        return None

    def add_node(self, raw_input: str, custom_name: str = "", local_port: int = 10809) -> dict[str, Any]:
        """添加一个代理节点，自动识别 vless:// 链接或 http:// 代理地址。"""
        text = (raw_input or "").strip()
        if not text:
            raise ValueError("节点信息不能为空")

        node_id = f"node_{uuid.uuid4().hex[:8]}"

        if text.startswith("vless://"):
            parsed = parse_vless_url(text)
            name = custom_name.strip() or parsed.get("name") or f"VLESS 节点 ({parsed.get('server')})"
            local_http_proxy = f"http://127.0.0.1:{local_port}"
            node = {
                "id": node_id,
                "name": name,
                "protocol": "vless",
                "raw_url": text,
                "proxy_url": local_http_proxy,  # 指向本地 Xray 监听端口
                "local_http_proxy": local_http_proxy,
                "server": parsed.get("server"),
                "port": parsed.get("port"),
                "network_type": parsed.get("type"),
                "security": parsed.get("security"),
                "parsed_data": parsed,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        else:
            # 普通 HTTP / SOCKS5 代理
            proxy_url = text
            if not proxy_url.startswith(("http://", "https://", "socks5://", "socks://")):
                proxy_url = f"http://{proxy_url}"
            name = custom_name.strip() or f"代理节点 ({proxy_url.replace('http://', '')})"
            node = {
                "id": node_id,
                "name": name,
                "protocol": "http" if not proxy_url.startswith("socks") else "socks5",
                "raw_url": text,
                "proxy_url": proxy_url,
                "local_http_proxy": proxy_url,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

        # 检查是否有完全相同的 raw_url，如果有则更新
        existing_idx = None
        for i, item in enumerate(self._nodes):
            if item.get("raw_url") == text:
                existing_idx = i
                break

        if existing_idx is not None:
            node["id"] = self._nodes[existing_idx]["id"]
            self._nodes[existing_idx] = node
        else:
            self._nodes.append(node)

        self.save()
        return node

    def delete_node(self, node_id: str) -> bool:
        """删除指定节点，并将绑定到该节点的采集器置为 direct 或 default。"""
        orig_len = len(self._nodes)
        self._nodes = [n for n in self._nodes if n.get("id") != node_id]
        # 解绑
        for k, v in list(self._bindings.items()):
            if v == node_id:
                self._bindings[k] = "default"
        self.save()
        return len(self._nodes) < orig_len

    # ------------------------------------------------------------- 采集器绑定控制
    def get_bindings(self) -> dict[str, str]:
        """获取所有采集器的绑定映射 {site_key: node_id}。"""
        return self._bindings

    def set_crawler_binding(self, site_key: str, node_id: str) -> dict[str, Any]:
        """为指定采集器绑定特定节点、指定直连或跟随默认。
        
        node_id 可选值:
        - 具体节点 id (例如 node_123456)
        - "direct": 强制直连（不走代理）
        - "default": 跟随全局默认配置
        """
        clean_key = (site_key or "").strip().lower()
        clean_target = (node_id or "").strip()
        if not clean_key:
            raise ValueError("site_key 不能为空")

        self._bindings[clean_key] = clean_target
        self.save()
        return {
            "site_key": clean_key,
            "target_node": clean_target,
            "effective_proxy": self.get_site_proxy(clean_key),
        }

    # ------------------------------------------------------------- 代理获取与环境注入
    def get_site_proxy(self, site_key: Optional[str] = None) -> Optional[str]:
        """计算指定采集器实际生效的代理 URL。"""
        if not site_key:
            return self._default_proxy_url if self._enabled and self._default_proxy_url else None

        clean_key = site_key.strip().lower()
        target = self._bindings.get(clean_key, "default")

        # 1. 显式设为直连
        if target == "direct":
            return None

        # 2. 绑定了具体节点
        if target and target != "default":
            node = self.get_node_by_id(target)
            if node:
                return node.get("proxy_url") or node.get("local_http_proxy")

        # 3. 跟随全局默认
        if self._enabled and self._default_proxy_url:
            return self._default_proxy_url

        return None

    def get_site_env(self, site_key: Optional[str] = None) -> dict[str, str]:
        """为特定采集器子进程生成专属的环境变量字典。"""
        proxy = self.get_site_proxy(site_key)
        if proxy:
            return {
                "HTTP_PROXY": proxy,
                "HTTPS_PROXY": proxy,
                "ALL_PROXY": proxy,
                "http_proxy": proxy,
                "https_proxy": proxy,
                "all_proxy": proxy,
            }
        return {}

    def get_proxy_url(self) -> Optional[str]:
        return self.get_site_proxy(None)

    def get_env(self) -> dict[str, str]:
        return self.get_site_env(None)

    # ------------------------------------------------------------- Xray 配置导出
    def export_xray_config(self, node_id: str, http_port: int = 10809, socks_port: int = 10808) -> dict[str, Any]:
        """将指定的 VLESS 节点转换为开箱即用的 Xray-core config.json。"""
        node = self.get_node_by_id(node_id)
        if not node:
            raise ValueError(f"未找到节点: {node_id}")

        if node.get("protocol") != "vless":
            raise ValueError("只有 VLESS 协议节点支持导出 Xray 核心配置文件")

        raw_url = node.get("raw_url", "")
        return generate_xray_config(raw_url, http_port=http_port, socks_port=socks_port)

    # ------------------------------------------------------------- 连通性测试
    async def test_connection(
        self,
        target_url: str = "https://www.google.com",
        custom_proxy: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """测试指定代理地址或节点的连通性与网络耗时。"""
        proxy = custom_proxy
        if node_id:
            node = self.get_node_by_id(node_id)
            if node:
                proxy = node.get("proxy_url")
        if proxy is None:
            proxy = self.get_proxy_url()

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(proxy=proxy, verify=False, timeout=8.0) as client:
                resp = await client.get(target_url)
                duration = round((time.monotonic() - start) * 1000, 1)
                return {
                    "ok": resp.status_code in (200, 301, 302),
                    "status_code": resp.status_code,
                    "duration_ms": duration,
                    "proxy_used": proxy or "直连",
                    "message": f"连接成功 (HTTP {resp.status_code}, 耗时 {duration}ms)",
                }
        except Exception as exc:
            duration = round((time.monotonic() - start) * 1000, 1)
            return {
                "ok": False,
                "status_code": 0,
                "duration_ms": duration,
                "proxy_used": proxy or "直连",
                "message": f"连接失败: {exc}",
            }


proxy_manager = ProxyManager()
