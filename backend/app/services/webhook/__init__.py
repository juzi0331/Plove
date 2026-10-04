"""外部机器人与 Webhook 自动化推送服务子包。

模块结构：
- config: 配置文件路径与持久化管理
- signing: 鉴权签名与速率限制器
- templates: 各通道格式化与简报模版
- dispatch: 统一分发调度与通道投递核心
"""

from __future__ import annotations

from app.services.webhook.config import (
    DEFAULT_CONFIG_PATH,
    _get_default_config_path,
    load_config,
    save_config,
)
from app.services.webhook.dispatch import (
    WebhookService,
    webhook_service,
)
from app.services.webhook.signing import (
    TelegramRateLimiter,
    _resolve_telegram_proxy,
)
from app.services.webhook.templates import (
    collect_daily_report_metrics,
    format_telegram_message,
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
