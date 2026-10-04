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
    console_url: str = Field(default="", description="管理后台公网或局域网访问地址（用于推送通知内快捷直达按钮）")


class TelegramVerifyRequest(BaseModel):
    bot_token: str = Field(description="Telegram Bot Token")
    proxy_url: str | None = Field(default="", description="可选的 HTTP/SOCKS5 代理地址")


class TelegramVerifyResult(BaseModel):
    ok: bool
    id: int = 0
    username: str = ""
    first_name: str = ""
    error: str | None = None


class TelegramDetectChatRequest(BaseModel):
    bot_token: str = Field(description="Telegram Bot Token")
    proxy_url: str | None = Field(default="", description="可选的 HTTP/SOCKS5 代理地址")


class TelegramDetectChatResult(BaseModel):
    ok: bool
    chat_id: str = ""
    chat_title: str = ""
    username: str = ""
    chat_type: str = ""
    error: str | None = None


class EventSubscriptions(BaseModel):
    circuit_break: bool = Field(default=True, description="内容源连续失败或熔断告警")
    circuit_recover: bool = Field(default=True, description="内容源自愈恢复通知")
    site_health_report: bool = Field(default=True, description="聚合内容源清单与连通性自检报告")
    code_activated: bool = Field(default=True, description="新激活码首次绑定激活通知")
    device_conflict: bool = Field(default=True, description="同码多设备抢线/冲突下线告警")
    security_alert: bool = Field(default=True, description="接口防刷与高频限流安全告警")
    proxy_offline: bool = Field(default=True, description="代理节点异常或高延迟报警")
    daily_report: bool = Field(default=False, description="每日系统流量与设备简报")
    system_startup: bool = Field(default=False, description="Plove 服务集群启动/重启就绪通知")
    fail_threshold: int = Field(default=3, ge=1, le=10, description="连续失败触发告警的阈值次数")


class WebhookConfigPayload(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    events: EventSubscriptions = Field(default_factory=EventSubscriptions)
    # 兼容性字段：旧配置文件若残留其他机器人配置，允许解析但不返回与对外暴露
    wechat_work: Any | None = Field(default=None, exclude=True)
    feishu: Any | None = Field(default=None, exclude=True)
    custom_http: Any | None = Field(default=None, exclude=True)


class WebhookTestRequest(BaseModel):
    channel: str = Field(default="telegram", description="测试通道：telegram")
    custom_text: str = Field(default="", description="自定义测试消息文本（留空发送标准测试卡片）")


class WebhookSendEventRequest(BaseModel):
    channel: str = Field(default="telegram", description="目标推送通道：telegram")
    event_type: str = Field(default="test", description="事件类型标识")
    title: str = Field(default="", description="自定义标题（留空时自动生成对应事件仿真内容）")
    content: str = Field(default="", description="自定义正文（留空时自动生成对应事件仿真描述）")
    fields: dict[str, Any] | None = Field(default=None, description="自定义附加字段字典")
    raw_html: bool = Field(default=False, description="是否为原生 Telegram HTML 格式（开启后不执行二次转义，原生渲染 b, code, i 等标签）")



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
