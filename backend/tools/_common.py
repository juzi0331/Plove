"""命令行工具的公共部分。

放在 ``_`` 开头是刻意的：它能被别的工具 import，但不会被当成一个"工具"。
"""

from __future__ import annotations

import sys
from pathlib import Path

#: 后端根目录（``tools/`` 的上一层）。挂到 sys.path 上，脚本才能 ``import app.*``
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def force_utf8() -> None:
    """Windows 控制台默认是 GBK，直接 print 中文会变乱码。

    爬虫那侧已经踩过这个坑（见 crawler/README.md），这里沿用同一套做法：
    JSON 与终端输出统一按 UTF-8 走。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - 不可重配置的流
            pass
