"""后台外部通知与 Webhook 自动化推送管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.errors import AppError, ErrorCode
from app.core.middleware import get_request_id
from app.core.security import is_safe_public_url
from app.schemas.envelope import Envelope, ok
from app.schemas.webhook import (
    TelegramVerifyRequest,
    TelegramVerifyResult,
    WebhookConfigPayload,
    WebhookLogsPayload,
    WebhookTestRequest,
    WebhookTestResult,
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
    # 防御保存恶意指向内网/云元数据的非公网 Webhook URL (SSRF)
    if payload.custom_http.url and payload.custom_http.url.strip():
        if not is_safe_public_url(payload.custom_http.url.strip()):
            raise AppError(ErrorCode.BAD_REQUEST, "自定义 Webhook 目标地址不合法或指向受限内网")
    if payload.wechat_work.webhook_url and payload.wechat_work.webhook_url.strip():
        if not is_safe_public_url(payload.wechat_work.webhook_url.strip()):
            raise AppError(ErrorCode.BAD_REQUEST, "企业微信 Webhook 目标地址不合法或指向受限内网")
    if payload.feishu.webhook_url and payload.feishu.webhook_url.strip():
        if not is_safe_public_url(payload.feishu.webhook_url.strip()):
            raise AppError(ErrorCode.BAD_REQUEST, "飞书 Webhook 目标地址不合法或指向受限内网")

    webhook_service.save(payload)
    return ok(webhook_service.get_config(), request_id)


@router.post("/test", response_model=Envelope[WebhookTestResult], summary="向指定机器人/Webhook渠道发送即时测试消息")
def test_webhook_channel(
    req: WebhookTestRequest,
    request_id: str = Depends(get_request_id),
) -> Envelope[WebhookTestResult]:
    title = "连通性测试消息"
    content = req.custom_text.strip() or "恭喜！Plove 外部告警推送通道已成功接入并完成连通性测试。"
    fields = {
        "测试通道": req.channel.upper(),
        "触发来源": "Plove Console",
        "状态": "通道链路正常",
    }
    result = webhook_service.send_to_channel(
        channel=req.channel,
        event_type="test",
        title=title,
        content=content,
        fields=fields,
    )
    return ok(result, request_id)


@router.post("/telegram/verify", response_model=Envelope[TelegramVerifyResult], summary="校验 Telegram Bot Token 并获取机器人信息")
def verify_telegram_bot(
    req: TelegramVerifyRequest,
    request_id: str = Depends(get_request_id),
) -> Envelope[TelegramVerifyResult]:
    result = webhook_service.verify_telegram(req.bot_token, req.proxy_url)
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
