from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from ..code_generator import generate_crawler_python_code
from ..extractor_html import HtmlNode, parse_html
from ...core.cleaner import clean_title, collapse_whitespace, safe_resolve_url
from ...core.http_client import HttpClient
from ...core.log import get_logger
from .detail_prober import default_detail_fields, extract_detail_heuristic, probe_detail_fields
from .models import SmartExploreResult, StructureInspectionResult
from .rule_builder import generate_default_rule
from .stream_sniffer import sniff_stream_url
from .taxonomy import discover_taxonomy_tree, extract_categories_heuristic
from .vod_extractor import extract_vod_list_heuristic

logger = get_logger("smart_agent")


class SmartAgent:
    """自动探测引擎。"""

    def __init__(self, target_url: str) -> None:
        self.target_url = target_url.strip()
        parsed = urllib.parse.urlparse(self.target_url)
        if not parsed.scheme:
            self.target_url = f"https://{self.target_url}"
            parsed = urllib.parse.urlparse(self.target_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        domain_parts = parsed.netloc.split(":")[0].split(".")
        clean_key = domain_parts[-2] if len(domain_parts) >= 2 else domain_parts[0]
        self.suggested_key = re.sub(r"[^a-zA-Z0-9_]", "", clean_key).lower()
        if not self.suggested_key or not self.suggested_key[0].isalpha():
            self.suggested_key = f"site_{self.suggested_key}"
        self.logs: list[str] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)
        logger.info("[SmartAgent] %s", msg)

    async def _resolve_entry_page(self, client: HttpClient, target_url: str) -> tuple[str, HtmlNode]:
        """请求目标页面，若遇到门禁页/过渡页/欢迎页，自动跟踪进入主入口。"""
        resp = await client.request("GET", target_url)
        self.log(f"源站响应状态码: {resp.status_code}")
        html = resp.text
        root = parse_html(html)

        anchors = root.select("a")
        if len(anchors) <= 6:
            for a in anchors:
                h = (a.attr("href") or "").strip()
                t = collapse_whitespace(a.text)
                if not h or h == "#" or h.startswith("javascript:"):
                    continue
                if any(w in t for w in ["进入", "進入", "18", "滿", "满", "成年", "agree", "enter", "continue", "首页", "首頁"]) or h in ("/home", "/index.html", "/main"):
                    if not h.startswith("http") or any(dom in h for dom in (self.base_url, self.suggested_key)):
                        next_url = safe_resolve_url(self.base_url, h)
                        self.log(f"检测到网站引导/准入过渡页，自动跟踪至主入口: {next_url}")
                        try:
                            next_resp = await client.request("GET", next_url)
                            if next_resp.status_code == 200 and len(next_resp.text) > len(html):
                                return next_resp.text, parse_html(next_resp.text)
                        except Exception as exc:
                            self.log(f"跟踪主入口异常: {exc}")
                        break
        return html, root

    async def explore(self) -> SmartExploreResult:
        self.log(f"开始连接目标站点: {self.target_url}")
        async with HttpClient(base_url=self.base_url) as client:
            html, root = await self._resolve_entry_page(client, self.target_url)

            text_body = html
            if text_body.strip().startswith("{") and text_body.strip().endswith("}"):
                self.log("检测到目标站为纯 JSON API 接口")
                return await self._explore_json(json.loads(text_body))
            else:
                self.log("检测到目标站为 HTML 网页形态，启动智能 DOM 聚类分析")
                return await self._explore_html(client, text_body)

    async def inspect_structure(self) -> StructureInspectionResult:
        """对目标站点进行可视化探测勘探。"""
        self.log(f"启动可视化结构勘探: {self.target_url}")
        async with HttpClient(base_url=self.base_url) as client:
            html, root = await self._resolve_entry_page(client, self.target_url)

            # 1. 站点名称
            og_site = root.select_first("meta[property='og:site_name'], meta[name='og:site_name']")
            if og_site and og_site.attr("content"):
                site_name = clean_title(og_site.attr("content").split(",")[0].split("-")[0].split("_")[0]) or self.suggested_key
            else:
                title_node = root.select_first("title")
                raw_title = title_node.text if title_node else self.suggested_key
                site_name = clean_title(raw_title.split("-")[0].split("_")[0].split("|")[0]) or self.suggested_key

            # 2. 深度导航与标签树勘探
            categories_tree, unassigned_tags = await discover_taxonomy_tree(client, self.base_url, root, html)
            self.log(f"识别出 {len(categories_tree)} 个候选一级分类，{len(unassigned_tags)} 个标签候选项")

            # 3. 采样详情页字段探测
            recommend = extract_vod_list_heuristic(self.base_url, root, categories=categories_tree)
            sample_video = recommend[0] if recommend else None
            detail_fields = default_detail_fields()

            if sample_video and sample_video.get("raw_href"):
                detail_url = safe_resolve_url(self.base_url, sample_video["raw_href"])
                self.log(f"采样详情页深入探测: {detail_url}")
                try:
                    detail_resp = await client.request("GET", detail_url)
                    detail_html = detail_resp.text
                    detail_root = parse_html(detail_html)
                    detail_fields = probe_detail_fields(self.base_url, sample_video, detail_root, detail_url, detail_html)
                except Exception as exc:
                    self.log(f"采样详情页探测异常: {exc}")

            return StructureInspectionResult(
                base_url=self.base_url,
                site_name=site_name,
                suggested_key=self.suggested_key,
                categories_tree=categories_tree,
                unassigned_tags=unassigned_tags,
                unassigned_tags_pool=unassigned_tags,
                detail_fields=detail_fields,
                sample_video=sample_video,
                html_preview=html[:3000],
                steps_log=self.logs,
            )

    async def _explore_html(self, client: HttpClient, html: str) -> SmartExploreResult:
        root = parse_html(html)

        # 1. 站点名称推测
        og_site = root.select_first("meta[property='og:site_name'], meta[name='og:site_name']")
        if og_site and og_site.attr("content"):
            site_name = clean_title(og_site.attr("content").split(",")[0].split("-")[0].split("_")[0]) or self.suggested_key
        else:
            title_node = root.select_first("title")
            raw_title = title_node.text if title_node else self.suggested_key
            site_name = clean_title(raw_title.split("-")[0].split("_")[0].split("|")[0]) or self.suggested_key
        self.log(f"推断站点名称: {site_name}")

        # 2. 启发式提取分类
        categories = extract_categories_heuristic(root)
        self.log(f"自动发现 {len(categories)} 个分类导航条目")

        # 3. 启发式聚类提取首页视频列表
        recommend = extract_vod_list_heuristic(self.base_url, root, categories=categories)
        self.log(f"自动发现 {len(recommend)} 部首页推荐视频")

        sample_detail = None
        sample_stream = None

        # 4. 深入第一部影片获取详情与播放地址
        if recommend:
            first_vod = recommend[0]
            vod_href = first_vod.get("raw_href")
            if vod_href:
                detail_url = safe_resolve_url(self.base_url, vod_href)
                self.log(f"深入探索样本详情页: {detail_url}")
                try:
                    detail_html = await client.get_text(detail_url)
                    detail_root = parse_html(detail_html)
                    sample_detail = extract_detail_heuristic(first_vod, detail_root, detail_url, html_content=detail_html)
                    self.log(f"成功提取详情: 《{sample_detail['video']['vod_name']}》，共 {len(sample_detail['episodes'])} 集")

                    # 5. 深入第一集探测播放流
                    if sample_detail["episodes"]:
                        first_ep = sample_detail["episodes"][0]
                        play_href = first_ep.get("play_id")
                        if play_href and play_href.startswith("/"):
                            play_url = safe_resolve_url(self.base_url, play_href)
                            self.log(f"深入嗅探第 1 集播放流页面: {play_url}")
                            play_html = await client.get_text(play_url)
                            sample_stream = sniff_stream_url(play_html)
                            if sample_stream:
                                self.log(f"嗅探到播放流直链: {sample_stream['url']}")
                            else:
                                self.log("未直接嗅探到 m3u8，尝试在详情页源码中搜索...")
                except Exception as exc:
                    self.log(f"深入详情页发生非致命异常: {exc}")

        # 6. 生成可运行的 SiteRule 与独立 Python 爬虫脚本
        generated_rule = generate_default_rule(self.suggested_key, self.base_url, site_name, categories, recommend)
        python_code = generate_crawler_python_code(
            key=self.suggested_key,
            name=site_name,
            base_url=self.base_url,
            categories=categories,
        )
        self.log(f"已自动生成合规单文件采集器脚本: sites/{self.suggested_key}.py (共 {len(python_code.splitlines())} 行)")

        return SmartExploreResult(
            base_url=self.base_url,
            site_name=site_name,
            suggested_key=self.suggested_key,
            data_type="html",
            categories=categories,
            recommend=recommend,
            sample_detail=sample_detail,
            sample_stream=sample_stream,
            generated_rule=generated_rule,
            generated_python_code=python_code,
            steps_log=self.logs,
        )

    async def _explore_json(self, data: Any) -> SmartExploreResult:
        return SmartExploreResult(
            base_url=self.base_url,
            site_name=self.suggested_key,
            suggested_key=self.suggested_key,
            data_type="json",
            categories=[],
            recommend=[],
            generated_rule={"key": self.suggested_key, "base_url": self.base_url, "data_type": "json"},
            steps_log=self.logs,
        )
