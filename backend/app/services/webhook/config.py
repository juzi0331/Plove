"""Webhook 服务配置文件路径与存取管理。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from app.schemas.webhook import WebhookConfigPayload

logger = logging.getLogger(__name__)


def _get_default_config_path() -> Path:
    backend_root = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = backend_root / "data"
    data_candidate = data_dir / "webhook_config.json"
    if data_candidate.is_file():
        return data_candidate
    legacy_candidate = backend_root / "webhook_config.json"
    if legacy_candidate.is_file():
        return legacy_candidate
    return data_candidate


DEFAULT_CONFIG_PATH = _get_default_config_path()


def load_config(config_path: Path) -> WebhookConfigPayload:
    """从磁盘加载 Webhook 配置并应用环境变量覆盖。"""
    cfg = WebhookConfigPayload()
    if config_path.is_file():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            cfg = WebhookConfigPayload.model_validate(data)
        except Exception as exc:
            logger.warning("读取 Webhook 配置文件失败: %s", exc)

    # 环境变量加固覆盖（敏感凭据优先走环境变量）
    if env_tg_token := os.environ.get("PLOVE_TELEGRAM_BOT_TOKEN"):
        cfg.telegram.bot_token = env_tg_token.strip()
    if env_tg_chat := os.environ.get("PLOVE_TELEGRAM_CHAT_ID"):
        cfg.telegram.chat_id = env_tg_chat.strip()
    if env_tg_proxy := os.environ.get("PLOVE_TELEGRAM_PROXY_URL"):
        cfg.telegram.proxy_url = env_tg_proxy.strip()
    if env_wechat := os.environ.get("PLOVE_WECHAT_WEBHOOK_URL"):
        cfg.wechat_work.webhook_url = env_wechat.strip()
    if env_feishu_url := os.environ.get("PLOVE_FEISHU_WEBHOOK_URL"):
        cfg.feishu.webhook_url = env_feishu_url.strip()
    if env_feishu_sec := os.environ.get("PLOVE_FEISHU_SECRET"):
        cfg.feishu.secret = env_feishu_sec.strip()
    if env_custom_url := os.environ.get("PLOVE_CUSTOM_HTTP_URL"):
        cfg.custom_http.url = env_custom_url.strip()
    if env_custom_token := os.environ.get("PLOVE_CUSTOM_HTTP_TOKEN"):
        cfg.custom_http.secret_token = env_custom_token.strip()

    return cfg


def save_config(config_path: Path, payload: WebhookConfigPayload) -> None:
    """持久化保存 Webhook 配置至 JSON 文件。"""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(payload.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.error("保存 Webhook 配置文件失败: %s", exc)
