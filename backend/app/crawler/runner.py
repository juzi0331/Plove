"""爬虫子进程执行器。

协议照抄 [crawler-plan.md](../../../docs/crawler-plan.md)，三条硬规矩：

* 爬虫的 stdout **只允许一行 JSON**，日志与栈一律走 stderr；
* 爬虫**正常退出码永远是 0**，失败用 ``ok:false`` 表达；
* **超时由我们负责** —— 爬虫不知道调用方的耐心，所以到点直接 kill，
  翻译成 ``UPSTREAM_TIMEOUT``。

为什么是子进程而不是 import：威胁模型是**稳定性隔离**，不是安全沙箱。
一个爬虫卡死或吃满内存，绝不能拖着整个 API 一起死。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger

logger = get_logger(__name__)

#: 站点 key 就是文件名，必须长得像模块名。
#: 这不只是洁癖 —— 不校验的话 ``../../etc/passwd`` 这种 key 会变成路径穿越。
SITE_KEY_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{1,63}$")

#: 播放类命令要多抓一个播放页，超时另算
PLAY_COMMANDS = frozenset({"play"})


def _get_proxy_for_site(crawler_dir: Path, key: str) -> str | None:
    """查找站点专属代理配置。

    优先级：
    1. 站点管理后台（SiteSetting / SitesView.vue）配置的独立代理与开关
    2. 环境变量 PROXY_{KEY}
    3. crawler/service/proxy_config.json 独立绑定或全局配置
    """
    # 1. 站点后台配置（UI 独立开关与地址）
    try:
        from app.services.site_settings import store
        cfg = store().config(key)
        if cfg is not None:
            if getattr(cfg, "proxy_enabled", False):
                url = (getattr(cfg, "proxy_url", "") or "").strip()
                if url:
                    return url
            elif getattr(cfg, "proxy_url", "").strip():
                # 填写了代理地址但开关处于关闭状态，说明运维明确要求该站走直连
                return None
    except Exception:
        pass

    # 2. 站点专属环境变量: PROXY_HUANGGUOAI_COM
    env_key = f"PROXY_{key.upper()}"
    if env_val := os.environ.get(env_key, "").strip():
        return env_val

    # 3. 检查 crawler/service/proxy_config.json 独立绑定
    cfg_path = crawler_dir / "service" / "proxy_config.json"
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            bindings = data.get("bindings", {})
            target = bindings.get(key.lower(), "default")
            if target == "direct":
                return None
            if target and target != "default":
                for node in data.get("nodes", []):
                    if node.get("id") == target:
                        return node.get("proxy_url") or node.get("local_http_proxy")
            # 兼容老版 sites 结构
            if "sites" in data and key.lower() in data["sites"]:
                s_cfg = data["sites"][key.lower()]
                if s_cfg.get("enabled") and s_cfg.get("proxy_url"):
                    return s_cfg["proxy_url"]
            # 跟随全局默认
            if data.get("enabled"):
                return data.get("default_proxy_url") or data.get("proxy_url")
        except Exception:
            pass
    return None


class CrawlerRunner:
    """按命令行协议执行一次爬虫命令。"""

    def __init__(
        self,
        sites_dir: Path,
        python: str | None = None,
        timeout: float = 8.0,
        timeout_play: float = 5.0,
    ) -> None:
        self.sites_dir = Path(sites_dir)
        #: 用**当前解释器**跑爬虫，保证本地与线上是同一条路径
        self.python = python or sys.executable
        self.timeout = timeout
        self.timeout_play = timeout_play

    def timeout_for(self, command: str, custom_timeout: float | None = None) -> float:
        if custom_timeout is not None and custom_timeout > 0:
            return float(custom_timeout)
        return self.timeout_play if command in PLAY_COMMANDS else self.timeout

    def script_for(self, key: str) -> Path:
        if not SITE_KEY_PATTERN.match(str(key)):
            raise AppError(ErrorCode.BAD_REQUEST, f"非法的站点 key: {key!r}")
        script = self.sites_dir / f"{key}.py"
        if not script.is_file():
            raise AppError(ErrorCode.NOT_FOUND, f"没有这个站点: {key}")
        return script

    def run(self, key: str, command: str, custom_timeout: float | None = None, **options: Any) -> Any:
        """执行并返回信封里的 ``data``；失败一律抛 :class:`AppError`。"""
        script = self.script_for(key)

        argv = [self.python, str(script), command]
        for name, value in options.items():
            if value is None:
                continue
            argv += [f"--{name}", str(value)]

        timeout = self.timeout_for(command, custom_timeout=custom_timeout)
        env = os.environ.copy()
        # 爬虫那侧 stdout 写死 UTF-8。Windows 上默认是 GBK，
        # 后端按 UTF-8 解析中文必然炸 —— 典型的"本地绿、上传炸"。
        env["PYTHONIOENCODING"] = "utf-8"
        env.setdefault("PYTHONUTF8", "1")

        # 确保子进程无论在任何工作目录下执行，都能精确加载 crawler_kit
        crawler_dir = self.sites_dir.parent
        project_root = crawler_dir.parent
        if crawler_dir.is_dir():
            env["CRAWLER_KIT_PATH"] = str(crawler_dir)
            existing_pp = env.get("PYTHONPATH", "")
            pp_parts = [str(crawler_dir), str(project_root)]
            if existing_pp:
                pp_parts.append(existing_pp)
            env["PYTHONPATH"] = os.pathsep.join(pp_parts)

        # 注入站点专属代理（支持单站独立代理绑定与开关）
        site_proxy = _get_proxy_for_site(crawler_dir, key)
        if site_proxy:
            env["HTTP_PROXY"] = site_proxy
            env["HTTPS_PROXY"] = site_proxy
            env["ALL_PROXY"] = site_proxy
            env["http_proxy"] = site_proxy
            env["https_proxy"] = site_proxy
            env["all_proxy"] = site_proxy
            env[f"PROXY_{key.upper()}"] = site_proxy
            logger.info("爬虫 key=%s 注入独立代理: %s", key, site_proxy)
        else:
            # 清理可能继承的宿主机全局代理环境变量，确保未开启代理的站点真正走直连！
            for p_env in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", f"PROXY_{key.upper()}"]:
                env.pop(p_env, None)

        logger.debug("跑爬虫 key=%s command=%s timeout=%ss", key, command, timeout)

        try:
            completed = subprocess.run(  # noqa: S603 - argv 是构造出来的，不过 shell
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                cwd=str(self.sites_dir) if self.sites_dir.is_dir() else None,
            )
        except subprocess.TimeoutExpired as exc:
            raise AppError(
                ErrorCode.UPSTREAM_TIMEOUT,
                f"{key} 的 {command} 超过 {timeout:g}s 没返回，已终止",
            ) from exc
        except OSError as exc:  # pragma: no cover - 解释器都起不来属于环境问题
            raise AppError(ErrorCode.INTERNAL, f"爬虫进程起不来: {exc}") from exc

        return self._parse(key, command, completed)

    # ------------------------------------------------------------------ 内部

    def _parse(self, key: str, command: str, completed: subprocess.CompletedProcess) -> Any:
        """解析 stdout 里那唯一一行 JSON。"""
        line = ""
        for candidate in reversed(completed.stdout.splitlines()):
            if candidate.strip():
                line = candidate.strip()
                break

        if not line:
            raise AppError(
                ErrorCode.UPSTREAM_PARSE_ERROR,
                f"{key} 的 {command} 没有任何输出（退出码 {completed.returncode}）",
            )

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AppError(
                ErrorCode.UPSTREAM_PARSE_ERROR,
                f"{key} 的 {command} stdout 不是合法 JSON: {line[:120]!r}",
            ) from exc

        if not isinstance(payload, dict) or "ok" not in payload:
            raise AppError(
                ErrorCode.UPSTREAM_PARSE_ERROR,
                f"{key} 的 {command} 输出不是合法信封",
            )

        if not payload["ok"]:
            error = payload.get("error") or {}
            raise AppError.from_crawler(
                str(error.get("code") or "UNKNOWN"),
                str(error.get("message") or f"{key} 的 {command} 失败"),
            )

        return payload.get("data")
