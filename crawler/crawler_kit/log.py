"""日志：**只写 stderr**。

硬规矩：stdout 只允许出现一行 JSON。任何调试输出走这里，
否则后端解析信封必然失败。级别用环境变量 ``CRAWLER_LOG`` 控制。
"""

from __future__ import annotations

import os
import sys

_ORDER = {"debug": 10, "info": 20, "warn": 30, "error": 40}
_LEVEL = os.environ.get("CRAWLER_LOG", "info").strip().lower()


def _emit(level: str, message: str) -> None:
    if _ORDER.get(level, 20) < _ORDER.get(_LEVEL, 20):
        return
    print(f"[{level.upper()}] {message}", file=sys.stderr, flush=True)


def debug(message: str) -> None:
    _emit("debug", message)


def info(message: str) -> None:
    _emit("info", message)


def warn(message: str) -> None:
    _emit("warn", message)


def error(message: str) -> None:
    _emit("error", message)


def success(message: str) -> None:
    _emit("info", message)
