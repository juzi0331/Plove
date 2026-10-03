"""站点分类控制与详情页清洗展示策略服务包。"""

from app.services.site_control.cache_policy import (
    get_site_cache_policy,
    save_site_cache_policy,
)
from app.services.site_control.category_rules import (
    apply_category_rules,
    check_category_allowed,
    format_category_display_name,
    get_category_rules_payload,
    get_home_display_category_plans,
    save_category_rules_payload,
)
from app.services.site_control.detail_policy import (
    apply_detail_policy,
    clean_text_with_patterns,
    get_cached_fastest_line,
    get_detail_policy_payload,
    probe_and_select_fastest_line,
    save_detail_policy_payload,
    set_cached_fastest_line,
)

__all__ = [
    "format_category_display_name",
    "get_category_rules_payload",
    "get_home_display_category_plans",
    "save_category_rules_payload",
    "apply_category_rules",
    "check_category_allowed",
    "get_detail_policy_payload",
    "save_detail_policy_payload",
    "clean_text_with_patterns",
    "get_cached_fastest_line",
    "set_cached_fastest_line",
    "probe_and_select_fastest_line",
    "apply_detail_policy",
    "get_site_cache_policy",
    "save_site_cache_policy",
]
