"""后台外部通知与 Webhook 自动化推送管理接口。"""

from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends

from app.core.middleware import get_request_id
from app.schemas.envelope import Envelope, ok
from app.schemas.webhook import (
    TelegramDetectChatRequest,
    TelegramDetectChatResult,
    TelegramVerifyRequest,
    TelegramVerifyResult,
    WebhookConfigPayload,
    WebhookLogsPayload,
    WebhookSendEventRequest,
    WebhookTestRequest,
    WebhookTestResult,
)
from app.services.webhook.templates import (
    collect_daily_report_metrics,
    collect_site_health_report,
)
from app.services.webhook_service import webhook_service

router = APIRouter(prefix="/webhooks", tags=["后台-外部通知与Webhook"])


@router.get("/config", response_model=Envelope[WebhookConfigPayload], summary="获取当前 Webhook 与机器人配置")
def get_webhook_config(request_id: str = Depends(get_request_id)) -> Envelope[WebhookConfigPayload]:
    return ok(webhook_service.get_config(), request_id)


@router.put("/config", response_model=Envelope[WebhookConfigPayload], summary="更新 Webhook 与机器人配置")
def update_webhook_config(
    payload: WebhookConfigPayload,
    request_id: str = Depends(get_request_id),
) -> Envelope[WebhookConfigPayload]:
    webhook_service.save(payload)
    return ok(webhook_service.get_config(), request_id)


@router.post("/test", response_model=Envelope[WebhookTestResult], summary="向 Telegram 发送即时测试消息")
def test_webhook_channel(
    req: WebhookTestRequest,
    request_id: str = Depends(get_request_id),
) -> Envelope[WebhookTestResult]:
    title = "连通性测试消息"
    content = req.custom_text.strip() or "恭喜！Plove Telegram 告警推送通道已成功接入并完成连通性测试。"
    fields = {
        "测试通道": "TELEGRAM BOT",
        "触发来源": "Plove Console",
        "状态": "通道链路正常",
    }
    result = webhook_service.send_to_channel(
        channel=req.channel or "telegram",
        event_type="test",
        title=title,
        content=content,
        fields=fields,
    )
    return ok(result, request_id)


@router.post("/send-event", response_model=Envelope[WebhookTestResult], summary="手动触发指定事件推送或自定义通知")
def send_webhook_event(
    req: WebhookSendEventRequest,
    request_id: str = Depends(get_request_id),
) -> Envelope[WebhookTestResult]:
    event_type = req.event_type.strip() or "test"
    channel = req.channel or "telegram"
    title = req.title.strip()
    content = req.content.strip()
    fields = dict(req.fields) if req.fields else {}

    # 若未自定义指定 title/content，则按各事件类型生成高拟真度的仿真预警卡片
    if event_type == "circuit_break":
        if not title:
            title = "内容源 [Jable] 触发熔断保护"
        if not content:
            content = "内容源 [Jable] 连续请求失败已达阈值 3 次，已进入熔断冷却状态（冷却时长 60 秒）。"
        if not fields:
            fields = {
                "故障源站": "Jable",
                "失败原因": "UPSTREAM_TIMEOUT",
                "连续失败": "3 次",
                "冷却时长": "60s",
            }
    elif event_type == "circuit_recover":
        if not title:
            title = "内容源 [Jable] 自愈恢复通知"
        if not content:
            content = "内容源 [Jable] 冷却期后探针请求成功，熔断保护已自动解除，节点恢复正常可用。"
        if not fields:
            fields = {
                "恢复源站": "Jable",
                "故障熔断时长": "65 秒",
                "当前健康度": "正常 (Healthy)",
            }
    elif event_type == "site_health_report":
        if not title or not content:
            r_title, r_content, r_fields = collect_site_health_report()
            title = title or r_title
            content = content or r_content
            fields = fields or r_fields
    elif event_type == "proxy_offline":
        if not title:
            title = "代理节点连通性异常/离线预警"
        if not content:
            content = "代理节点「香港优质专线 01」TLS 握手超时，未能成功建立到上游的连接。"
        if not fields:
            fields = {
                "节点名称": "香港优质专线 01",
                "协议类型": "VLESS",
                "失败原因": "TLS Handshake Timeout",
            }
    elif event_type == "code_activated":
        if not title:
            title = "激活码首次绑定激活通知"
        if not content:
            content = "激活码 PLOV-****-9821 已被设备「iPhone 16 Pro Max」首次成功绑定激活。"
        if not fields:
            fields = {
                "激活码": "PLOV-****-9821",
                "绑定设备": "iPhone 16 Pro Max",
                "有效时长": "720 小时 (30天)",
                "到期时间": "2026-11-03 18:30:00",
            }
    elif event_type == "device_conflict":
        if not title:
            title = "同码多设备抢线与冲突下线告警"
        if not content:
            content = "激活码 PLOV-****-9821 发生设备抢占，新设备「iPad Air」上线并将原设备「iPhone 16 Pro」顶替下线。"
        if not fields:
            fields = {
                "激活码": "PLOV-****-9821",
                "新上线设备": "iPad Air",
                "被顶替设备": "iPhone 16 Pro",
                "安全提示": "如非本人切换设备，激活码可能已被外泄共享",
            }
    elif event_type == "security_alert":
        if not title:
            title = "接口防刷与高频限流安全告警"
        if not content:
            content = "来源 IP [198.51.100.24] 在接口范围「redeem」触发高频访问限流拦截，疑似恶意探测或暴力猜解。"
        if not fields:
            fields = {
                "拦截范围": "redeem (激活兑换)",
                "来源 IP": "198.51.100.24",
                "限制策略": "5 次 / 60 秒",
                "处置策略": "自动拦截并返回 429 冷却",
            }
    elif event_type == "daily_report":
        if not title or not content:
            r_title, r_content, r_fields = collect_daily_report_metrics()
            title = title or r_title
            content = content or r_content
            fields = fields or r_fields
    elif event_type == "system_startup":
        if not title:
            title = "Plove 服务集群已就绪"
        if not content:
            content = "Plove 核心后端服务已成功启动就绪，数据库引擎连接建立，监控看门狗正常运行。"
        if not fields:
            fields = {
                "运行环境": "production",
                "API 版本": "v1",
                "就绪时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
    elif event_type == "custom":
        if not title:
            title = "系统公告与运营通知"
        if not content:
            content = "这是一条由管理员在控制台手动分发的即时通知。"
        is_html_content = req.raw_html or any(tag in content for tag in ("<b>", "<code>", "<i>", "<blockquote>", "<pre>", "<tg-spoiler>"))
        if not fields and not is_html_content:
            fields = {
                "发布人": "系统管理员",
                "发布渠道": "Telegram 运营群",
            }

    is_raw_html = req.raw_html or (event_type == "custom" and any(tag in content for tag in ("<b>", "<code>", "<i>", "<blockquote>", "<pre>", "<tg-spoiler>")))

    result = webhook_service.send_to_channel(
        channel=channel,
        event_type=event_type,
        title=title,
        content=content,
        fields=fields,
        raw_html=is_raw_html,
    )
    return ok(result, request_id)



@router.post("/telegram/verify", response_model=Envelope[TelegramVerifyResult], summary="校验 Telegram Bot Token 并获取机器人信息")
def verify_telegram_bot(
    req: TelegramVerifyRequest,
    request_id: str = Depends(get_request_id),
) -> Envelope[TelegramVerifyResult]:
    result = webhook_service.verify_telegram(req.bot_token, req.proxy_url or "")
    return ok(result, request_id)


@router.post("/telegram/detect-chat", response_model=Envelope[TelegramDetectChatResult], summary="自动从 Telegram 抓取最新与 Bot 互动的 Chat ID")
def detect_telegram_chat(
    req: TelegramDetectChatRequest,
    request_id: str = Depends(get_request_id),
) -> Envelope[TelegramDetectChatResult]:
    result = webhook_service.detect_telegram_chat(req.bot_token, req.proxy_url or "")
    return ok(result, request_id)


@router.get("/logs", response_model=Envelope[WebhookLogsPayload], summary="获取最近 Webhook 投递日志")
def get_webhook_logs(
    limit: int = 30,
    request_id: str = Depends(get_request_id),
) -> Envelope[WebhookLogsPayload]:
    logs = webhook_service.get_logs(limit=limit)
    return ok(WebhookLogsPayload(logs=logs, total=len(logs)), request_id)


@router.post("/logs/clear", response_model=Envelope[dict[str, bool]], summary="清空 Webhook 投递历史日志")
def clear_webhook_logs(request_id: str = Depends(get_request_id)) -> Envelope[dict[str, bool]]:
    webhook_service.clear_logs()
    return ok({"cleared": True}, request_id)
