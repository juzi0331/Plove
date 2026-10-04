from __future__ import annotations

from typing import Any


def generate_default_rule(
    suggested_key: str,
    base_url: str,
    site_name: str,
    categories: list[dict[str, str]],
    recommend: list[dict[str, Any]],
) -> dict[str, Any]:
    """根据勘探出的特征自动推导并生成可长久复用的 SiteRule 配置。"""
    return {
        "key": suggested_key,
        "name": site_name,
        "version": "1.0.0",
        "base_url": base_url,
        "mode": "direct",
        "data_type": "html",
        "home": {
            "path": "/",
            "method": "GET",
            "static_categories": categories,
            "recommend_container": ".module-item, .vodlist_item, li",
            "recommend_item": {
                "vod_id": {
                    "selector": "a",
                    "attribute": "href",
                    "regex": r"/(\d+)\.html",
                },
                "vod_name": {"selector": ".title, h3, a"},
                "vod_pic": {"selector": "img", "attribute": "data-original"},
                "vod_remarks": {"selector": ".module-item-text, .remarks, span"},
            },
        },
        "detail": {
            "path": "/detail/{id}.html",
            "method": "GET",
            "title_extractor": {"selector": "h1, .page-title"},
            "pic_extractor": {"selector": "img", "attribute": "data-original"},
            "desc_extractor": {"selector": ".video-info-content, .desc, p"},
            "episodes_container": "a[href*='/play/']",
            "episode_item": {
                "ep_name": {"selector": ""},
                "play_id": {"attribute": "href"},
            },
        },
        "play": {
            "path": "{play_id}",
            "method": "GET",
            "play_url_extractor": {
                "type": "regex",
                "regex": r"""(?:["']|\b)(https?://[^\s"'<>]+\.m3u8[^\s"'<>]*)(?:["']|\b)""",
            },
            "format": "m3u8",
        },
    }
