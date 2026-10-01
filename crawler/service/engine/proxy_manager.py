"""代理管理器：支持配置本地代理（如 v2rayN http://127.0.0.1:10809, Clash http://127.0.0.1:7890 等）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Optional
import httpx

from ..core.log import get_logger

logger = get_logger("proxy_manager")


class ProxyManager:
    """集中式代理管理器：负责存储配置、控制环境变量、注入子进程和测试连通性。"""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or Path(__file__).resolve().parents[1] / "proxy_config.json"
        self._enabled: bool = False
        self._proxy_url: str = "http://127.0.0.1:10809"
        self.load()

    def load(self) -> None:
        if self.config_path.is_file():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self._enabled = bool(data.get("enabled", False))
                self._proxy_url = str(data.get("proxy_url", "http://127.0.0.1:10809")).strip()
            except Exception as exc:
                logger.warning("读取代理配置失败: %s", exc)
        self._apply_env()

    def save(self) -> None:
        try:
            self.config_path.write_text(
                json.dumps(
                    {"enabled": self._enabled, "proxy_url": self._proxy_url},
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("保存代理配置失败: %s", exc)
        self._apply_env()

    def _apply_env(self) -> None:
        """根据当前状态设置或清除当前主进程与后续子进程的代理环境变量。"""
        if self._enabled and self._proxy_url:
            os.environ["HTTP_PROXY"] = self._proxy_url
            os.environ["HTTPS_PROXY"] = self._proxy_url
            os.environ["ALL_PROXY"] = self._proxy_url
            os.environ["http_proxy"] = self._proxy_url
            os.environ["https_proxy"] = self._proxy_url
            os.environ["all_proxy"] = self._proxy_url
            logger.info("已启用本地网络代理: %s", self._proxy_url)
        else:
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                os.environ.pop(k, None)
            logger.info("已停用本地网络代理 (系统直连)")

    def get_config(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "proxy_url": self._proxy_url,
        }

    def set_config(self, enabled: bool, proxy_url: str) -> dict[str, Any]:
        self._enabled = bool(enabled)
        if proxy_url:
            self._proxy_url = str(proxy_url).strip()
        self.save()
        return self.get_config()

    def get_proxy_url(self) -> Optional[str]:
        return self._proxy_url if self._enabled and self._proxy_url else None

    def get_env(self) -> dict[str, str]:
        if self._enabled and self._proxy_url:
            return {
                "HTTP_PROXY": self._proxy_url,
                "HTTPS_PROXY": self._proxy_url,
                "ALL_PROXY": self._proxy_url,
                "http_proxy": self._proxy_url,
                "https_proxy": self._proxy_url,
                "all_proxy": self._proxy_url,
            }
        return {}

    async def test_connection(self, target_url: str = "https://www.google.com") -> dict[str, Any]:
        """测试指定代理地址的连通性与网络耗时。"""
        proxy = self._proxy_url if self._enabled and self._proxy_url else None
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(proxy=proxy, verify=False, timeout=8.0) as client:
                resp = await client.get(target_url)
                duration = round((time.monotonic() - start) * 1000, 1)
                return {
                    "ok": resp.status_code in (200, 301, 302),
                    "status_code": resp.status_code,
                    "duration_ms": duration,
                    "message": f"连接成功 (HTTP {resp.status_code}, 耗时 {duration}ms)",
                }
        except Exception as exc:
            duration = round((time.monotonic() - start) * 1000, 1)
            return {
                "ok": False,
                "status_code": 0,
                "duration_ms": duration,
                "message": f"连接失败: {exc}",
            }


proxy_manager = ProxyManager()
