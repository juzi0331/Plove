"""统一日志。

后端的日志只写 **stderr**；爬虫的日志走它自己的 stderr，不经过这里。
两边唯一的交点是信封里的 ``request_id`` —— 出问题时用它从网关日志串到爬虫 stderr。
"""

from __future__ import annotations

import logging
import sys

from app.core.config import Settings

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(settings: Settings) -> None:
    """在应用启动时调一次。``force=True`` 是为了盖掉 uvicorn 自己的配置。"""
    level = settings.log_level.upper()
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stderr,
        force=True,
    )
    # uvicorn 会自己配一遍日志，不显式设置的话级别会被它改回去
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
