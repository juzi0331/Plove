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
