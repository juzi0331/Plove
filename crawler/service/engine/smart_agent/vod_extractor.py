from __future__ import annotations

import re
from typing import Any, Optional

from ..extractor_html import HtmlNode
from ...core.cleaner import clean_title, collapse_whitespace, is_placeholder_image, safe_resolve_url


def extract_vod_list_heuristic(
    base_url: str,
    root: HtmlNode,
    categories: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """启发式聚类提取首页视频列表。"""
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # 扫描含有 img 和链接的卡片容器
    card_selectors = [
        ".module-item",
        ".vodlist_item",
        ".v-item",
        ".video-item",
        ".list-item",
        ".card",
        "li",
    ]

    nodes: list[HtmlNode] = []
    for sel in card_selectors:
        matched = root.select(sel)
        if len(matched) >= 4:
            nodes = matched
            break

    if not nodes:
        # 兜底寻找包含 img 和 a 的节点
        for a in root.select("a"):
            if a.select_first("img"):
                nodes.append(a)

    cat_hrefs: set[str] = set()
    if categories:
        for c in categories:
            raw = c.get("raw_href")
            if raw:
                cat_hrefs.add(raw)
            tid = c.get("tid")
            if tid:
                cat_hrefs.add(f"/cat/{tid}.html")
                cat_hrefs.add(f"/type/{tid}.html")

    for n in nodes:
        a_tag = n if n.tag == "a" else n.select_first("a")
        if not a_tag:
            continue
        href = a_tag.attr("href")
        if not href or href == "#" or "javascript:" in href:
            continue

        # 严格过滤：分类页面绝对不能当作视频
        if href.startswith("/cat/") or "/cat/" in href or href in cat_hrefs:
            continue

        # 提取影片 ID
        vod_id = ""
        m_post = re.search(r"/post/([a-zA-Z0-9_-]+)\.html", href)
        if m_post:
            vod_id = m_post.group(1)
        else:
            m_vod = re.search(r"/(?:detail|vod|v|show)/(\d+)", href)
            if m_vod:
                vod_id = m_vod.group(1)
            else:
                m_alt = re.search(r"/(\d+)\.html", href)
                if m_alt:
                    vod_id = m_alt.group(1)
                else:
                    clean_href = re.sub(r"[^\w-]", "", href.strip("/"))
                    if clean_href:
                        vod_id = clean_href

        if not vod_id or vod_id in seen_ids:
            continue

        # 寻找标题
        title = ""
        for t_sel in [".title", "h3", "h4", "h2", ".name", "span"]:
            tnode = n.select_first(t_sel)
            if tnode and tnode.text:
                title = clean_title(tnode.text)
                if title:
                    break
        if not title:
            title = clean_title(a_tag.attr("title") or a_tag.text)

        if not title or len(title) < 2 or title in ("更多", "换一换", "排行榜"):
            continue

        # 寻找封面图
        pic = ""
        img_tag = n.select_first("img")
        if img_tag:
            pic = img_tag.attr("data-original") or img_tag.attr("data-src") or img_tag.attr("src")
            pic = safe_resolve_url(base_url, pic)
            if is_placeholder_image(pic):
                pic = ""

        # 寻找备注状态
        remarks = ""
        for r_sel in [".module-item-text", ".remarks", ".pic-text", ".badge", ".text-right", ".status"]:
            rnode = n.select_first(r_sel)
            if rnode and rnode.text:
                remarks = collapse_whitespace(rnode.text)
                break

        seen_ids.add(vod_id)
        results.append({
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "raw_href": href,
        })

        if len(results) >= 24:
            break

    return results
