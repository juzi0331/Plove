"""后台管理公共校验与后处理助手，消除跨模块重复逻辑。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.deps import commit_now
from app.api.v1.admin._audit import audit
from app.core.errors import AppError, ErrorCode
from app.crawler.registry import SiteRegistry
from app.schemas.admin import AdminSiteActionResult
from app.schemas.envelope import Envelope, ok
from app.services import site_service
from app.services.site_settings import SiteSettingsStore


def require_known_site(registry: SiteRegistry, key: str) -> None:
    """在操作之前确认这个源真的存在。

    不确认的话，一个拼错的 key 会在库里静默生成一条无效记录或异常。
    """
    if key not in registry.keys():
        raise AppError(ErrorCode.NOT_FOUND, f"没有这个源：{key}")


def after_site_write(
    db: Session,
    registry: SiteRegistry,
    store: SiteSettingsStore,
    key: str,
    action: str,
    request_id: str,
    message: str,
) -> Envelope[AdminSiteActionResult]:
    """写操作共用的收尾：先落库、再刷快照、再记审计日志。"""
    commit_now(db)
    store.refresh(db, force=True)
    audit(action, request_id, site=key)
    return ok(
        AdminSiteActionResult(
            message=message,
            site=site_service.site_item(registry, store, key),
        ),
        request_id,
    )


def save_system_setting_json(db: Session, key: str, data: dict) -> None:
    """持久化 system_settings JSON 配置，消除重复的查询/插入代码。"""
    import json
    from app.models.system_setting import SystemSetting

    val_json = json.dumps(data, ensure_ascii=False)
    row = db.query(SystemSetting).filter_by(key=key).first()
    if not row:
        db.add(SystemSetting(key=key, value_json=val_json))
    else:
        row.value_json = val_json


def preheat_single_site(registry: SiteRegistry, cache: object, site: str) -> object | None:
    """单站首页预热与信息提取。"""
    import time
    from app.schemas.admin_extended import SitePreheatDetail
    from app.services import catalog_service

    t_site = time.perf_counter()
    try:
        home_data = catalog_service.home(registry, cache, site, force=True)  # type: ignore
        meta = registry.meta(site)
        return SitePreheatDetail(
            site=site,
            site_name=meta.name if meta else site,
            categories_count=len(home_data.categories),
            categories=[c.name for c in home_data.categories[:8] if c.name],
            recommend_count=len(home_data.recommend),
            recommend_titles=[r.vod_name for r in home_data.recommend[:8] if r.vod_name],
            sample_posters=[r.vod_pic for r in home_data.recommend if r.vod_pic][:4],
            elapsed_ms=round((time.perf_counter() - t_site) * 1000, 2),
        )
    except Exception:
        return None


