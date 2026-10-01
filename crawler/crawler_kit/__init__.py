"""crawler_kit —— 所有爬虫共用的工具箱。

硬约束：站点爬虫只允许 ``import crawler_kit`` + Python 标准库。
理由有三条 ——

1. 线上不必为每个爬虫准备依赖；
2. 后端做白名单校验时边界清晰；
3. 本地与线上能力完全一致，杜绝"本地绿、上传炸"。
"""

from __future__ import annotations

from . import audit, clean, cli, errors, gate, http, log, parse
from .audit import audit_script_ast, get_crawler_runner_env
from .errors import CrawlerError
from .gate import CookieGate
from .http import Client, Response
from .parse import (
    Node,
    find_m3u8,
    find_media_urls,
    first_image,
    parse_html,
    select,
    select_one,
    select_visible,
)

__version__ = "1.0.0"

__all__ = [
    "Client",
    "CookieGate",
    "CrawlerError",
    "Node",
    "Response",
    "__version__",
    "clean",
    "cli",
    "errors",
    "find_m3u8",
    "find_media_urls",
    "first_image",
    "gate",
    "http",
    "log",
    "parse",
    "parse_html",
    "select",
    "select_one",
    "select_visible",
]
