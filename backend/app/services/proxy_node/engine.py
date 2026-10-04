"""Xray-core 内置守护进程与一键安装管理器。"""

from __future__ import annotations

import atexit
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
from typing import Any, Optional
import urllib.request
import zipfile

from app.core.logging import get_logger
from app.services.proxy_node.vless import generate_unified_xray_config

logger = get_logger("xray_engine")


class XrayEngineManager:
    """Xray-core 内置守护进程与一键安装管理器。"""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._last_error: Optional[str] = None
        self._managed_ports: list[int] = []
        self._managed_nodes: list[str] = []
        atexit.register(self.stop_engine)

    def get_bin_dir(self) -> Path:
        base_dir = Path(__file__).resolve().parents[3]
        bin_dir = base_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        return bin_dir

    def find_binary(self) -> Optional[Path]:
        exe_name = "xray.exe" if os.name == "nt" else "xray"
        candidates = [
            self.get_bin_dir() / exe_name,
            Path(__file__).resolve().parents[4] / "bin" / exe_name,
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
        """为所有 VLESS 节点（或默认待机）启动统一的 Xray 代理进程。"""
        bin_p = self.find_binary()
        if not bin_p:
            return {"running": False, "error": "未安装 Xray 核心引擎"}

        vless_nodes = [n for n in nodes if n.get("protocol") == "vless" and n.get("raw_url")]

        self.stop_engine()

        cfg = generate_unified_xray_config(vless_nodes)
        config_path = self.get_bin_dir().parent / "data" / "xray_unified.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

        try:
            if os.name != "nt":
                try:
                    bin_p.chmod(bin_p.stat().st_mode | 0o755)
                except Exception as exc:
                    logger.warning("chmod xray binary failed: %s", exc)

            if os.name != "nt" and not os.access(bin_p, os.X_OK):
                self._last_error = f"Xray 二进制文件缺少执行权限: {bin_p}，请在终端执行: chmod +x {bin_p}"
                return {"running": False, "error": self._last_error}

            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

            env = dict(os.environ)
            env["XRAY_LOCATION_ASSET"] = str(bin_p.parent)

            proc = subprocess.Popen(
                [str(bin_p), "run", "-c", str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                cwd=str(bin_p.parent),
                env=env,
            )
            self._proc = proc
            time.sleep(0.6)
            if proc.poll() is not None:
                err_out = ""
                try:
                    out_text, err_text = proc.communicate(timeout=0.5)
                    err_out = (err_text or out_text or "").strip()
                except Exception:
                    pass
                self._proc = None
                self._last_error = f"Xray 启动后异常退出: {err_out}" if err_out else "Xray 启动后异常退出，请检查节点配置或端口 10809 是否被占用"
                return {"running": False, "error": self._last_error}

            self._last_error = None
            if vless_nodes:
                self._managed_ports = [int(n.get("local_port", 10809)) for n in vless_nodes]
                self._managed_nodes = [str(n.get("name", "")) for n in vless_nodes]
            else:
                self._managed_ports = [10809]
                self._managed_nodes = ["默认就绪监听 (直连待机)"]

            logger.info("Xray 引擎启动成功 (PID %s), 监听端口: %s", proc.pid, self._managed_ports)
            return {
                "running": True,
                "pid": proc.pid,
                "managed_ports": self._managed_ports,
                "managed_nodes": self._managed_nodes,
                "message": "Xray 引擎已成功启动并在端口 10809 就绪" if not vless_nodes else "Xray 引擎已成功启动并接管 VLESS 节点转发",
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
        if vless_nodes:
            ports = [int(n.get("local_port", 10809)) for n in vless_nodes]
            names = [str(n.get("name", "")) for n in vless_nodes]
        else:
            ports = [10809] if is_running else []
            names = ["默认就绪监听 (直连待机)"] if is_running else []

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
