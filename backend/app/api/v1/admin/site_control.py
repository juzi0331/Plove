"""后台 — 站点分类与详情页清洗策略控制。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    commit_now,
    get_db,
    get_registry,
    get_site_settings,
)
from app.api.v1.admin._audit import audit
from app.api.v1.admin._helpers import require_known_site
from app.core.middleware import get_request_id
from app.crawler.registry import SiteRegistry
from app.schemas.admin_extended import SiteCachePolicy
from app.schemas.admin_site_control import (
    SiteCategoryRulePayload,
    SiteCategoryRuleUpdateRequest,
    SiteDetailPolicyPayload,
    SiteDetailPolicyUpdateRequest,
)
from app.schemas.envelope import Envelope, ok
from app.services import site_control as site_control_service
from app.services.site_settings import SiteSettingsStore

router = APIRouter(tags=["后台-站点规则控制"])


@router.get("/sites/{key}/categories", response_model=Envelope[SiteCategoryRulePayload], summary="获取站点分类控制规则")
def get_site_categories(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteCategoryRulePayload]:
    """拉取源站真实分类并合并后台保存的隐藏、重命名、排序和子分类规则。"""
    require_known_site(registry, key)
    payload = site_control_service.get_category_rules_payload(registry, store, key)
    return ok(payload, request_id)


@router.put("/sites/{key}/categories", response_model=Envelope[SiteCategoryRulePayload], summary="更新站点分类控制规则")
def update_site_categories(
    key: str,
    payload: SiteCategoryRuleUpdateRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteCategoryRulePayload]:
    """批量更新分类隐藏/重命名/排序/子分类及默认推荐分类。"""
    require_known_site(registry, key)
    res = site_control_service.save_category_rules_payload(db, store, key, payload)
    commit_now(db)
    store.refresh(db, force=True)
    audit("update_site_categories", request_id, key=key, count=len(payload.rules))
    return ok(res, request_id)


@router.get("/sites/{key}/detail-policy", response_model=Envelope[SiteDetailPolicyPayload], summary="获取详情页策略")
def get_site_detail_policy(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteDetailPolicyPayload]:
    """获取广告过滤模式、线路名称映射、集数命名规则与兜底海报。"""
    require_known_site(registry, key)
    payload = site_control_service.get_detail_policy_payload(store, key)
    return ok(payload, request_id)


@router.put("/sites/{key}/detail-policy", response_model=Envelope[SiteDetailPolicyPayload], summary="更新详情页策略")
def update_site_detail_policy(
    key: str,
    payload: SiteDetailPolicyUpdateRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteDetailPolicyPayload]:
    """更新详情页广告清洗词汇、线路映射、集数命名及海报配置。"""
    require_known_site(registry, key)
    res = site_control_service.save_detail_policy_payload(db, key, payload)
    commit_now(db)
    store.refresh(db, force=True)
    audit("update_site_detail_policy", request_id, key=key)
    return ok(res, request_id)


@router.get("/sites/{key}/cache-policy", response_model=Envelope[SiteCachePolicy], summary="获取单站独立缓存策略")
def get_site_cache_policy(
    key: str,
    request_id: str = Depends(get_request_id),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteCachePolicy]:
    """读取某站点的 home_ttl, category_ttl, detail_ttl。"""
    require_known_site(registry, key)
    policy = site_control_service.get_site_cache_policy(store, key)
    return ok(policy, request_id)


@router.put("/sites/{key}/cache-policy", response_model=Envelope[SiteCachePolicy], summary="更新单站独立缓存策略")
def update_site_cache_policy(
    key: str,
    payload: SiteCachePolicy,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db),
    registry: SiteRegistry = Depends(get_registry),
    store: SiteSettingsStore = Depends(get_site_settings),
) -> Envelope[SiteCachePolicy]:
    """保存某站点的独立缓存策略。"""
    require_known_site(registry, key)
    policy = site_control_service.save_site_cache_policy(db, key, payload)
    store.refresh(db, force=True)
    audit("update_site_cache_policy", request_id, key=key)
    return ok(policy, request_id)
