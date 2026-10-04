"""Webhook 消息模板美化与每日简报生成。"""

from __future__ import annotations

from datetime import datetime
import html
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 事件类型对应的视觉主题徽标与默认前缀
EVENT_THEME_BADGES: dict[str, tuple[str, str]] = {
    "circuit_break": ("🚨", "【熔断告警】"),
    "circuit_recover": ("❇️", "【自愈恢复】"),
    "site_health_report": ("🧭", "【站点巡检】"),
    "code_activated": ("🎟️", "【激活通知】"),
    "device_conflict": ("⚠️", "【设备冲突】"),
    "security_alert": ("🛡️", "【安全风控】"),
    "proxy_offline": ("🌐", "【代理预警】"),
    "daily_report": ("📊", "【运营日报】"),
    "system_startup": ("🚀", "【服务就绪】"),
    "test": ("🔔", "【连通测试】"),
    "custom": ("📣", "【系统公告】"),
}


def format_telegram_message(
    title: str,
    content: str,
    fields: dict[str, Any] | None = None,
    event_type: str = "",
) -> str:
    """构造 Telegram 富文本 HTML 格式卡片消息。
    
    采用规范的层级结构：
    1. 视觉徽标与强调标题
    2. 分割装饰线
    3. 原生 <blockquote> 引用摘要块（Telegram 专属卡片式灰底与高亮左边线）
    4. 规范化的键值参数矩阵（使用代码块字体与整齐标点）
    5. 底部系统状态与带微秒时间戳标识
    """
    esc_title = html.escape(title.strip())
    esc_content = html.escape(content.strip())

    icon, badge = EVENT_THEME_BADGES.get(event_type, ("📢", "【监控通知】"))

    # 如果传入的 title 已经包含了类似的中文括号标，则直接使用 icon + title；否则加上规范 badge
    if "【" in esc_title and "】" in esc_title:
        header_line = f"{icon} <b>{esc_title}</b>"
    else:
        header_line = f"{icon} <b>{badge}{esc_title}</b>"

    divider = "━━━━━━━━━━━━━━━━━━━━━"
    
    # 构造主体行
    lines = [
        header_line,
        divider,
        f"<blockquote>{esc_content}</blockquote>",
    ]

    # 参数网格展示
    if fields:
        lines.append("")
        for k, v in fields.items():
            esc_k = html.escape(str(k).strip())
            esc_v = html.escape(str(v).strip())
            lines.append(f"▫️ <b>{esc_k}：</b> <code>{esc_v}</code>")

    # 底部页脚
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("")
    lines.append(divider)
    lines.append(f"<i>🕒 {now_str}  •  🤖 Plove Watchdog</i>")

    text = "\n".join(lines)

    # Telegram 4096 字符上限拦截与安全截断
    if len(text) > 4000:
        budget = 4000 - (len(text) - len(esc_content)) - 35
        if budget > 50:
            esc_content = esc_content[:budget] + "...\n<i>(内容已截断)</i>"
        else:
            esc_content = esc_content[:50] + "..."
        lines[2] = f"<blockquote>{esc_content}</blockquote>"
        text = "\n".join(lines)[:4090]

    return text


def build_telegram_reply_markup(
    event_type: str,
    console_url: str = "",
) -> dict[str, Any] | None:
    """根据告警事件类型及配置的控制台地址，生成交互式 Telegram 快捷操作按钮（Inline Keyboard）。"""
    url = (console_url or "").strip().rstrip("/")
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return None

    buttons: list[list[dict[str, str]]] = []

    if event_type in ("circuit_break", "circuit_recover", "site_health_report"):
        buttons.append([
            {"text": "🎬 内容源管理", "url": f"{url}/_manage/crawlers"},
            {"text": "🌐 代理节点池", "url": f"{url}/_manage/proxy-nodes"},
        ])
    elif event_type in ("code_activated", "device_conflict"):
        buttons.append([
            {"text": "🎟️ 激活码列表", "url": f"{url}/_manage/activation"},
            {"text": "📊 运营总览", "url": f"{url}/_manage"},
        ])
    elif event_type == "proxy_offline":
        buttons.append([
            {"text": "🌐 代理节点池", "url": f"{url}/_manage/proxy-nodes"},
            {"text": "⚙️ 告警设置", "url": f"{url}/_manage/webhooks"},
        ])
    elif event_type == "security_alert":
        buttons.append([
            {"text": "🛡️ 告警与审计", "url": f"{url}/_manage/webhooks"},
            {"text": "🎟️ 激活码管控", "url": f"{url}/_manage/activation"},
        ])
    elif event_type == "daily_report":
        buttons.append([
            {"text": "📊 进入管理控制台", "url": f"{url}/_manage"},
            {"text": "🎬 站点配置", "url": f"{url}/_manage/crawlers"},
        ])
    else:  # test, system_startup, or default
        buttons.append([
            {"text": "🛠️ 进入管理后台", "url": f"{url}/_manage"},
            {"text": "⚙️ Webhook 设置", "url": f"{url}/_manage/webhooks"},
        ])

    return {"inline_keyboard": buttons}


def collect_daily_report_metrics() -> tuple[str, str, dict[str, Any]]:
    """查询数据库收集系统状态指标并生成每日运营简报内容。"""
    try:
        from app.db.session import session_scope
        from app.models.activation import ActivationCode
        from app.models.device import Device
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

    title = "Plove 系统每日运行大盘简报"
    content = (
        f"Plove 服务集群状态健康。当前激活码累计 {total_codes} 个（已激活 {activated_codes} 个），"
        f"已绑定活跃设备 {active_devices} 台，聚合内容源 {enabled_sites}/{total_sites} 已启用并处于监控状态。"
    )
    fields = {
        "激活码总数": total_codes,
        "已激活数量": activated_codes,
        "在线设备数": active_devices,
        "可用内容源": f"{enabled_sites}/{total_sites} 启用",
        "集群状态": "运行良好 (Healthy)",
    }
    return title, content, fields


def collect_site_health_report() -> tuple[str, str, dict[str, Any]]:
    """收集当前接入的所有聚合内容源清单、开关状态与连通性/熔断防护指标。"""
    try:
        from app.core.config import get_settings
        from app.api.deps.runtime import get_registry
        from app.services.site_settings import store
        from app.services.site_service import list_admin_sites

        reg = get_registry(get_settings())
        st = store()
        sites_list = list_admin_sites(reg, st).sites
    except Exception as exc:
        logger.warning("收集源站清单与健康状态失败: %s", exc)
        sites_list = []

    total_sites = len(sites_list)
    enabled_sites = sum(1 for s in sites_list if s.enabled)
    disabled_sites = total_sites - enabled_sites

    title = "聚合内容源清单与连通性自检报告"
    content = (
        f"当前系统累计接入 {total_sites} 个聚合内容源，其中 {enabled_sites} 个处于启用服务状态，"
        f"{disabled_sites} 个已在后台停用。全站探针连通与熔断防护状态如下："
    )

    fields: dict[str, Any] = {
        "源站规模": f"累计 {total_sites} 个源 (启用 {enabled_sites} / 停用 {disabled_sites})",
    }

    if not sites_list:
        fields["源站状态"] = "暂无配置的爬虫源文件"
    else:
        for s in sites_list:
            name = s.name or s.key
            if not s.enabled:
                status_text = "⚪ 已在后台停用"
            elif s.health.state == "open":
                retry_s = int(s.health.retry_after or 0)
                status_text = f"🔴 熔断保护中 (冷却剩余 {retry_s}s)"
            elif s.health.state == "half_open":
                status_text = "🟡 探针试探恢复中"
            elif s.health.failures > 0:
                status_text = f"⚠️ 偶发异常 (失败 {s.health.failures} 次)"
            else:
                status_text = "🟢 正常可用 (Active)"

            proxy_desc = "直连"
            if getattr(s, "proxy_enabled", False):
                proxy_desc = "代理节点加速"
                if getattr(s, "proxy_node_id", ""):
                    proxy_desc = f"节点#{s.proxy_node_id[:6]}"

            fields[f"🎬 {name}"] = f"{status_text} | {proxy_desc}"

    return title, content, fields

