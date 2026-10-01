"""通用规则采集引擎调度器。

连接 SiteRule、网络层与 Extractor，完成对任意站点的标准化调度与契约交付。
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Optional

from .extractor_html import extract_html_field, parse_html
from .extractor_json import extract_json_field, get_json_path_value
from .models import SiteRule
from ..core.cleaner import clean_title, is_placeholder_image, safe_resolve_url
from ..core.errors import CrawlerServiceError, ErrorCode
from ..core.http_client import HttpClient
from ..core.log import get_logger

logger = get_logger("scraper")


class UniversalScraper:
    """通用抓取执行引擎。"""

    def __init__(self, rule: SiteRule) -> None:
        self.rule = rule

    async def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """统一执行入口：action 为 home / category / detail / play / search。"""
        handler = getattr(self, f"_action_{action}", None)
        if not handler:
            raise CrawlerServiceError(
                ErrorCode.UNSUPPORTED,
                f"站点 {self.rule.key} 不支持或未实现动作: {action}",
            )
        return await handler(**kwargs)

    # ------------------------------------------------------------- 动作实现

    async def _action_meta(self) -> dict[str, Any]:
        return {
            "key": self.rule.key,
            "name": self.rule.name,
            "version": self.rule.version,
            "base_url": self.rule.base_url,
            "mode": self.rule.mode,
            "data_type": self.rule.data_type,
        }

    async def _action_home(self) -> dict[str, Any]:
        if not self.rule.home:
            raise CrawlerServiceError(ErrorCode.UNSUPPORTED, "该站点未配置 home 首页规则")

        conf = self.rule.home
        url = safe_resolve_url(self.rule.base_url, conf.path)
        categories = []
        recommend = []

        if conf.static_categories:
            categories.extend(conf.static_categories)

        async with HttpClient(
            base_url=self.rule.base_url,
            headers=self.rule.custom_headers,
        ) as client:
            if self.rule.data_type == "json":
                data = await client.get_json(url)
                # 提取分类
                if conf.categories_container and conf.category_item:
                    cat_nodes = get_json_path_value(data, conf.categories_container) or []
                    for node in cat_nodes:
                        tid = extract_json_field(node, conf.category_item.tid)
                        name = clean_title(
                            extract_json_field(node, conf.category_item.name),
                            self.rule.ad_patterns,
                        )
                        if tid and name:
                            categories.append({"tid": tid, "name": name})

                # 提取推荐
                if conf.recommend_container and conf.recommend_item:
                    items = get_json_path_value(data, conf.recommend_container) or []
                    for item in items:
                        v = self._parse_json_vod_item(item, conf.recommend_item)
                        if v:
                            recommend.append(v)
            else:
                html = await client.get_text(url, encoding=self.rule.encoding)
                root = parse_html(html)

                # 提取分类
                if conf.categories_container and conf.category_item:
                    cat_nodes = root.select(conf.categories_container)
                    for node in cat_nodes:
                        tid = extract_html_field(node, conf.category_item.tid, self.rule.base_url)
                        name = clean_title(
                            extract_html_field(node, conf.category_item.name, self.rule.base_url),
                            self.rule.ad_patterns,
                        )
                        if tid and name:
                            categories.append({"tid": tid, "name": name})

                # 提取推荐
                if conf.recommend_container and conf.recommend_item:
                    nodes = root.select(conf.recommend_container)
                    for node in nodes:
                        v = self._parse_html_vod_item(node, conf.recommend_item)
                        if v:
                            recommend.append(v)

        return {"categories": categories, "recommend": recommend}

    async def _action_category(self, tid: str, page: int = 1) -> dict[str, Any]:
        if not self.rule.category:
            raise CrawlerServiceError(ErrorCode.UNSUPPORTED, "该站点未配置 category 规则")

        conf = self.rule.category
        path = conf.path.format(tid=urllib.parse.quote(str(tid)), page=page)
        url = safe_resolve_url(self.rule.base_url, path)
        videos = []
        has_more = False

        async with HttpClient(
            base_url=self.rule.base_url,
            headers=self.rule.custom_headers,
        ) as client:
            if self.rule.data_type == "json":
                data = await client.get_json(url)
                items = get_json_path_value(data, conf.list_container) or []
                for item in items:
                    v = self._parse_json_vod_item(item, conf.item)
                    if v:
                        videos.append(v)
                if conf.has_more_extractor:
                    raw_hm = extract_json_field(data, conf.has_more_extractor)
                    has_more = raw_hm.lower() in ("true", "1", "yes")
                else:
                    has_more = len(videos) >= conf.page_size
            else:
                html = await client.get_text(url, encoding=self.rule.encoding)
                root = parse_html(html)
                nodes = root.select(conf.list_container)
                for node in nodes:
                    v = self._parse_html_vod_item(node, conf.item)
                    if v:
                        videos.append(v)
                if conf.has_more_extractor:
                    raw_hm = extract_html_field(root, conf.has_more_extractor, self.rule.base_url)
                    has_more = bool(raw_hm and raw_hm.strip())
                else:
                    has_more = len(videos) >= conf.page_size

        return {"videos": videos, "page": page, "has_more": has_more}

    async def _action_detail(self, id: str) -> dict[str, Any]:
        if not self.rule.detail:
            raise CrawlerServiceError(ErrorCode.UNSUPPORTED, "该站点未配置 detail 规则")

        conf = self.rule.detail
        path = conf.path.format(id=urllib.parse.quote(str(id)))
        url = safe_resolve_url(self.rule.base_url, path)

        async with HttpClient(
            base_url=self.rule.base_url,
            headers=self.rule.custom_headers,
        ) as client:
            if self.rule.data_type == "json":
                data = await client.get_json(url)
                title = clean_title(
                    extract_json_field(data, conf.title_extractor),
                    self.rule.ad_patterns,
                )
                pic = extract_json_field(data, conf.pic_extractor, self.rule.base_url) if conf.pic_extractor else ""
                desc = clean_title(
                    extract_json_field(data, conf.desc_extractor),
                    self.rule.ad_patterns,
                ) if conf.desc_extractor else ""
                remarks = extract_json_field(data, conf.remarks_extractor) if conf.remarks_extractor else ""

                vod_item = {
                    "vod_id": str(id),
                    "vod_name": title,
                    "vod_pic": "" if is_placeholder_image(pic) else pic,
                    "vod_remarks": remarks,
                }

                # 提取剧集列表
                episodes = []
                ep_nodes = get_json_path_value(data, conf.episodes_container) or []
                for idx, ep_node in enumerate(ep_nodes, start=1):
                    ep_name = extract_json_field(ep_node, conf.episode_item.ep_name)
                    play_id = extract_json_field(ep_node, conf.episode_item.play_id)
                    line_val = extract_json_field(ep_node, conf.episode_item.line) if conf.episode_item.line else None
                    episodes.append({
                        "ep_index": idx,
                        "ep_name": ep_name or f"第{idx}集",
                        "play_id": play_id or str(idx),
                        "line": line_val,
                    })

                lines = []
                if conf.lines_container and conf.line_item:
                    line_nodes = get_json_path_value(data, conf.lines_container) or []
                    for lnode in line_nodes:
                        lcode = extract_json_field(lnode, conf.line_item.line)
                        lname = extract_json_field(lnode, conf.line_item.name)
                        if lcode and lname:
                            lines.append({"line": lcode, "name": lname, "count": len(episodes)})

                return {
                    "video": vod_item,
                    "desc": desc,
                    "episodes": episodes,
                    "lines": lines,
                }
            else:
                html = await client.get_text(url, encoding=self.rule.encoding)
                root = parse_html(html)

                title = clean_title(
                    extract_html_field(root, conf.title_extractor, self.rule.base_url, full_html_text=html),
                    self.rule.ad_patterns,
                )
                pic = extract_html_field(root, conf.pic_extractor, self.rule.base_url, full_html_text=html) if conf.pic_extractor else ""
                desc = clean_title(
                    extract_html_field(root, conf.desc_extractor, self.rule.base_url, full_html_text=html),
                    self.rule.ad_patterns,
                ) if conf.desc_extractor else ""
                remarks = extract_html_field(root, conf.remarks_extractor, self.rule.base_url, full_html_text=html) if conf.remarks_extractor else ""

                vod_item = {
                    "vod_id": str(id),
                    "vod_name": title,
                    "vod_pic": "" if is_placeholder_image(pic) else pic,
                    "vod_remarks": remarks,
                }

                episodes = []
                ep_nodes = root.select(conf.episodes_container)
                for idx, node in enumerate(ep_nodes, start=1):
                    ep_name = extract_html_field(node, conf.episode_item.ep_name, self.rule.base_url)
                    play_id = extract_html_field(node, conf.episode_item.play_id, self.rule.base_url)
                    line_val = extract_html_field(node, conf.episode_item.line, self.rule.base_url) if conf.episode_item.line else None
                    episodes.append({
                        "ep_index": idx,
                        "ep_name": ep_name or f"第{idx}集",
                        "play_id": play_id or str(idx),
                        "line": line_val,
                    })

                lines = []
                if conf.lines_container and conf.line_item:
                    line_nodes = root.select(conf.lines_container)
                    for lnode in line_nodes:
                        lcode = extract_html_field(lnode, conf.line_item.line, self.rule.base_url)
                        lname = extract_html_field(lnode, conf.line_item.name, self.rule.base_url)
                        if lcode and lname:
                            lines.append({"line": lcode, "name": lname, "count": len(episodes)})

                return {
                    "video": vod_item,
                    "desc": desc,
                    "episodes": episodes,
                    "lines": lines,
                }

    async def _action_play(
        self,
        id: str = "",
        ep: int = 1,
        play_id: str = "",
        line: str = "",
    ) -> dict[str, Any]:
        if not self.rule.play:
            raise CrawlerServiceError(ErrorCode.UNSUPPORTED, "该站点未配置 play 规则")

        conf = self.rule.play
        # 支持路径占位符
        target_path = conf.path.format(
            id=id,
            ep=ep,
            play_id=urllib.parse.quote(play_id or ""),
            line=line or "",
        )
        url = safe_resolve_url(self.rule.base_url, target_path)

        async with HttpClient(
            base_url=self.rule.base_url,
            headers=self.rule.custom_headers,
        ) as client:
            play_url = ""
            if self.rule.data_type == "json":
                data = await client.get_json(url)
                play_url = extract_json_field(data, conf.play_url_extractor, self.rule.base_url)
            else:
                html = await client.get_text(url, encoding=self.rule.encoding)
                root = parse_html(html)
                play_url = extract_html_field(
                    root,
                    conf.play_url_extractor,
                    self.rule.base_url,
                    full_html_text=html,
                )

        if not play_url:
            raise CrawlerServiceError(ErrorCode.PARSE_ERROR, "无法嗅探或提取到有效播放流地址")

        return {
            "url": play_url,
            "format": conf.format,
            "headers": conf.headers or {},
        }

    async def _action_search(self, kw: str, page: int = 1) -> dict[str, Any]:
        if not self.rule.search:
            raise CrawlerServiceError(ErrorCode.UNSUPPORTED, "该站点不支持搜索功能")

        conf = self.rule.search
        path = conf.path.format(kw=urllib.parse.quote(str(kw)), page=page)
        url = safe_resolve_url(self.rule.base_url, path)
        videos = []
        has_more = False

        async with HttpClient(
            base_url=self.rule.base_url,
            headers=self.rule.custom_headers,
        ) as client:
            if self.rule.data_type == "json":
                data = await client.get_json(url)
                items = get_json_path_value(data, conf.list_container) or []
                for item in items:
                    v = self._parse_json_vod_item(item, conf.item)
                    if v:
                        videos.append(v)
            else:
                html = await client.get_text(url, encoding=self.rule.encoding)
                root = parse_html(html)
                nodes = root.select(conf.list_container)
                for node in nodes:
                    v = self._parse_html_vod_item(node, conf.item)
                    if v:
                        videos.append(v)

        return {"videos": videos, "page": page, "has_more": len(videos) > 0}

    # ------------------------------------------------------------- 辅助解析

    def _parse_html_vod_item(self, node: Any, rule: Any) -> Optional[dict[str, str]]:
        vod_id = extract_html_field(node, rule.vod_id, self.rule.base_url)
        vod_name = clean_title(
            extract_html_field(node, rule.vod_name, self.rule.base_url),
            self.rule.ad_patterns,
        )
        if not vod_id or not vod_name:
            return None

        vod_pic = ""
        if rule.vod_pic:
            raw_pic = extract_html_field(node, rule.vod_pic, self.rule.base_url)
            vod_pic = "" if is_placeholder_image(raw_pic) else raw_pic

        vod_remarks = ""
        if rule.vod_remarks:
            vod_remarks = extract_html_field(node, rule.vod_remarks, self.rule.base_url)

        return {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": vod_remarks,
        }

    def _parse_json_vod_item(self, data: Any, rule: Any) -> Optional[dict[str, str]]:
        vod_id = extract_json_field(data, rule.vod_id)
        vod_name = clean_title(
            extract_json_field(data, rule.vod_name),
            self.rule.ad_patterns,
        )
        if not vod_id or not vod_name:
            return None

        vod_pic = ""
        if rule.vod_pic:
            raw_pic = extract_json_field(data, rule.vod_pic, self.rule.base_url)
            vod_pic = "" if is_placeholder_image(raw_pic) else raw_pic

        vod_remarks = ""
        if rule.vod_remarks:
            vod_remarks = extract_json_field(data, rule.vod_remarks)

        return {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": vod_remarks,
        }
