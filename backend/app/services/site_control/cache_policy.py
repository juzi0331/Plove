"""单站独立缓存策略持久化服务。"""

from __future__ import annotations

import json
from sqlalchemy.orm import Session

from app.schemas.admin_extended import SiteCachePolicy
from app.services.site_settings import SiteSettingsStore


def get_site_cache_policy(store: SiteSettingsStore, key: str) -> SiteCachePolicy:
    """读取某站点的独立缓存策略。"""
    config = store.config(key)
    raw = getattr(config, "cache_policy_json", "{}")
    try:
        data = json.loads(raw or "{}")
        return SiteCachePolicy(**data)
    except Exception:
        return SiteCachePolicy()


def save_site_cache_policy(
    db: Session,
    key: str,
    policy: SiteCachePolicy,
) -> SiteCachePolicy:
    """持久化保存某站点的独立缓存策略。"""
    from app.db.session import commit_now
    from app.models.site_setting import SiteSetting

    setting = db.query(SiteSetting).filter_by(key=key).first()
    if not setting:
        setting = SiteSetting(key=key)
        db.add(setting)

    setting.cache_policy_json = policy.model_dump_json()
    commit_now(db)
    from app.services import site_settings
    site_settings.store().refresh(db, force=True)
    return policy
