"""图片防盗链代理配置持久化与规则管理。"""

from __future__ import annotations

import json
from typing import Any

from app.core.clock import utcnow
from app.db.session import commit_now
from app.models.system_setting import SystemSetting
from app.schemas.admin_extended import ImageDecryptionRule, ImageProxyConfig

PROXY_CONFIG_KEY = "image_proxy_config"
_cached_config: ImageProxyConfig | None = None


def get_image_proxy_config(db: Any = None) -> ImageProxyConfig:
    """获取图片代理配置（支持缓存）。"""
    global _cached_config
    if _cached_config is not None:
        return _cached_config
    if db is None:
        try:
            from app.db.session import get_session_factory
            with get_session_factory()() as session:
                return get_image_proxy_config(session)
        except Exception:
            _cached_config = ImageProxyConfig()
            return _cached_config
    try:
        row = db.query(SystemSetting).filter_by(key=PROXY_CONFIG_KEY).first()
        if not row or not row.value_json:
            _cached_config = ImageProxyConfig()
            return _cached_config
        data = json.loads(row.value_json)
        _cached_config = ImageProxyConfig(**data)
        return _cached_config
    except Exception:
        _cached_config = ImageProxyConfig()
        return _cached_config


def update_image_proxy_config(db: Any, payload: ImageProxyConfig) -> ImageProxyConfig:
    """更新图片代理配置并持久化。"""
    global _cached_config
    payload.updated_at = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    row = db.query(SystemSetting).filter_by(key=PROXY_CONFIG_KEY).first()
    if not row:
        row = SystemSetting(key=PROXY_CONFIG_KEY, value_json=payload.model_dump_json())
        db.add(row)
    else:
        row.value_json = payload.model_dump_json()
    commit_now(db)
    _cached_config = payload
    return payload


def register_or_update_decryption_rule(db: Any, rule: ImageDecryptionRule) -> None:
    """注册或更新指定的图片解密规则（如爬虫脚本自动侦测并同步到后台）。"""
    cfg = get_image_proxy_config(db)
    existing_idx = -1
    for idx, r in enumerate(cfg.decryption_rules):
        if (rule.id and r.id == rule.id) or (rule.site_key and r.site_key == rule.site_key):
            existing_idx = idx
            break
    if existing_idx >= 0:
        cfg.decryption_rules[existing_idx] = rule
    else:
        cfg.decryption_rules.append(rule)
    update_image_proxy_config(db, cfg)
