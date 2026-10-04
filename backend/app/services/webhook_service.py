"""外部机器人与 Webhook 自动化推送服务（向后兼容导出层）。

业务逻辑已模块化重构至 app.services.webhook 子包：
- app.services.webhook.config: 配置持久化与环境变量读取
- app.services.webhook.signing: 鉴权签名与速率限制
- app.services.webhook.templates: 各通道消息模版与简报统计
- app.services.webhook.dispatch: 统一分发与通道投递
"""

from __future__ import annotations

from app.services.webhook import (
    DEFAULT_CONFIG_PATH,
    TelegramRateLimiter,
    WebhookService,
    _get_default_config_path,
    _resolve_telegram_proxy,
    collect_daily_report_metrics,
    format_telegram_message,
    load_config,
    save_config,
    webhook_service,
)

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "TelegramRateLimiter",
    "WebhookService",
    "_get_default_config_path",
    "_resolve_telegram_proxy",
    "collect_daily_report_metrics",
    "format_telegram_message",
    "load_config",
    "save_config",
    "webhook_service",
]
