"""Webhook 各通道消息模板格式化与每日简报生成。"""

from __future__ import annotations

from datetime import datetime
import html
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def format_telegram_message(
    title: str,
    content: str,
    fields: dict[str, Any] | None = None,
) -> str:
    """构造 Telegram HTML 格式消息，支持自动转义与 4096 字符上限截断。"""
    esc_title = html.escape(title)
    esc_content = html.escape(content)
    lines = [f"<b>[Plove 监控通知] {esc_title}</b>", "", esc_content]
    if fields:
        lines.append("")
        for k, v in fields.items():
            lines.append(f"• <b>{html.escape(str(k))}</b>: <code>{html.escape(str(v))}</code>")
    lines.append(f"\n<i>时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")
    text = "\n".join(lines)

    # Telegram 4096 字符上限拦截与截断
    if len(text) > 4000:
        budget = 4000 - (len(text) - len(esc_content)) - 35
        if budget > 50:
            esc_content = esc_content[:budget] + "...\n<i>(内容已截断)</i>"
        else:
            esc_content = esc_content[:50] + "..."
        lines[2] = esc_content
        text = "\n".join(lines)[:4090]

    return text


def format_wechat_markdown(
    title: str,
    content: str,
    fields: dict[str, Any] | None = None,
) -> str:
    """构造企业微信群机器人 Markdown 格式消息。"""
    md = f"### [Plove 监控告警] {title}\n>{content}\n\n"
    if fields:
        for k, v in fields.items():
            md += f">**{k}**: <font color=\"comment\">{v}</font>\n"
    md += f"\n>推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return md


def format_feishu_content(
    title: str,
    content: str,
    fields: dict[str, Any] | None = None,
) -> str:
    """构造飞书群机器人纯文本格式消息。"""
    text_lines = [f"【Plove 告警通知】{title}", "", content]
    if fields:
        text_lines.append("")
        for k, v in fields.items():
            text_lines.append(f"{k}: {v}")
    text_lines.append(f"\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(text_lines)


def format_custom_http_payload(
    event_type: str,
    title: str,
    content: str,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造自定义 HTTP Webhook 统一 JSON 载荷。"""
    return {
        "event": event_type,
        "title": title,
        "content": content,
        "fields": fields or {},
        "timestamp": int(time.time()),
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def collect_daily_report_metrics() -> tuple[str, str, dict[str, Any]]:
    """查询数据库收集系统状态指标并生成每日运营简报内容。"""
    try:
        from app.db.session import session_scope
        from app.models.activation import ActivationCode, Device
        from app.models.site_setting import SiteSetting
        from sqlalchemy import func, select

        with session_scope() as session:
            total_codes = session.scalar(select(func.count(ActivationCode.id))) or 0
            activated_codes = (
                session.scalar(
                    select(func.count(ActivationCode.id)).where(ActivationCode.activated_at.is_not(None))
                )
                or 0
            )
            active_devices = session.scalar(select(func.count(Device.id))) or 0
            total_sites = session.scalar(select(func.count(SiteSetting.key))) or 0
            enabled_sites = (
                session.scalar(select(func.count(SiteSetting.key)).where(SiteSetting.enabled.is_(True)))
                or 0
            )
    except Exception as exc:
        logger.warning("每日简报收集数据库指标失败: %s", exc)
        total_codes = activated_codes = active_devices = total_sites = enabled_sites = 0

    title = "Plove 每日运行简报"
    content = (
        f"系统状态正常。激活码累计 {total_codes} 个（已激活 {activated_codes} 个），"
        f"当前绑定设备 {active_devices} 台，聚合内容源 {enabled_sites}/{total_sites} 已启用。"
    )
    fields = {
        "激活码总数": total_codes,
        "已激活数量": activated_codes,
        "绑定设备数": active_devices,
        "可用内容源": f"{enabled_sites}/{total_sites}",
        "简报生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return title, content, fields
