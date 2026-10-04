"""外部机器人与 Webhook 推送的 Pydantic 规范。"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token: str = Field(default="", description="Telegram Bot Token，如 123456:ABC-DEF")
    chat_id: str = Field(default="", description="接收消息的 Chat ID / Group ID")
    proxy_url: str = Field(default="", description="可选的 HTTP/SOCKS5 代理地址，如 http://127.0.0.1:10809")
    bot_username: str = Field(default="", description="自动识别的 Bot @username")
    bot_name: str = Field(default="", description="自动识别的 Bot 名称")


class TelegramVerifyRequest(BaseModel):
    bot_token: str = Field(description="Telegram Bot Token")
    proxy_url: str = Field(default="", description="可选的 HTTP/SOCKS5 代理地址")


class TelegramVerifyResult(BaseModel):
    ok: bool
    id: int = 0
    username: str = ""
    first_name: str = ""
    error: str | None = None


class WeChatWorkConfig(BaseModel):
    enabled: bool = False
    webhook_url: str = Field(default="", description="企业微信群机器人 Webhook 地址")


class FeishuConfig(BaseModel):
    enabled: bool = False
    webhook_url: str = Field(default="", description="飞书群自定义机器人 Webhook 地址")
    secret: str = Field(default="", description="可选的飞书签名校验 Secret")


class CustomHttpConfig(BaseModel):
    enabled: bool = False
    url: str = Field(default="", description="自定义 HTTP 回调地址（POST JSON）")
    secret_token: str = Field(default="", description="签名或请求头校验 Token（X-Plove-Token）")


class EventSubscriptions(BaseModel):
    circuit_break: bool = Field(default=True, description="内容源连续失败或熔断告警")
    code_activated: bool = Field(default=True, description="新激活码激活与使用通知")
    proxy_offline: bool = Field(default=True, description="代理节点异常或高延迟报警")
    daily_report: bool = Field(default=False, description="每日系统流量与设备简报")
    fail_threshold: int = Field(default=3, ge=1, le=10, description="连续失败触发告警的阈值次数")


class WebhookConfigPayload(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    wechat_work: WeChatWorkConfig = Field(default_factory=WeChatWorkConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    custom_http: CustomHttpConfig = Field(default_factory=CustomHttpConfig)
    events: EventSubscriptions = Field(default_factory=EventSubscriptions)


class WebhookTestRequest(BaseModel):
    channel: str = Field(description="测试通道：telegram | wechat_work | feishu | custom_http")
    custom_text: str = Field(default="", description="自定义测试消息文本（留空发送标准测试卡片）")


class WebhookTestResult(BaseModel):
    channel: str
    ok: bool
    status_code: int = 0
    duration_ms: int = 0
    message: str = ""
    error: str | None = None


class WebhookDeliveryLogItem(BaseModel):
    id: str
    channel: str
    event_type: str
    title: str
    status: str = Field(description="success | failed")
    status_code: int = 0
    duration_ms: int = 0
    error: str | None = None
    sent_at: str
    payload_summary: str = ""


class WebhookLogsPayload(BaseModel):
    logs: list[WebhookDeliveryLogItem] = Field(default_factory=list)
    total: int = 0
