"""结构化日志输出。"""

import logging
import sys

from ..config import settings


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"crawler_service.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    level_name = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level_name)
    return logger

