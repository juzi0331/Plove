"""后台管理写操作的审计记录工具。"""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


def audit(action: str, request_id: str, **fields: object) -> None:
    """写操作的审计记录。

    只记 INFO 一行：这些操作频率极低（人工点击），但解释力很强。
    **不要在这里记设备令牌** —— 那是客户端凭证，日志里不该有它的明文。
    """
    detail = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("后台操作 action=%s %s request_id=%s", action, detail, request_id)
