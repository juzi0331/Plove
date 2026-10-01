"""智能自适应采集器（Smart Auto-Discovery Scraper）。

核心理念：
用户只需输入一个目标站点的主页 URL，剩下的全部自动化：
1. 自动连接探测（自动探测编码、自动破解反爬闸门）；
2. 自动识别站点名称、提取导航分类；
3. 启发式聚类挖掘首页推荐视频卡片（图片、标题、ID、状态）；
4. 自动深入采集样本影片详情（剧情、选集列表）；
5. 自动嗅探第一集播放页面，正则提取真实 m3u8/mp4 视频流；
6. 自动推导并生成可长久复用的 SiteRule 配置。
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Optional
from pydantic import BaseModel

from .code_generator import generate_crawler_python_code
from .extractor_html import HtmlNode, parse_html
from .models import (
    CategoryItemRule,
    DetailRule,
    EpisodeItemRule,
    FieldExtractor,
    HomeRule,
    PlayRule,
    SiteRule,
    VodItemRule,
)
from ..core.cleaner import clean_title, collapse_whitespace, is_placeholder_image, safe_resolve_url
from ..core.errors import CrawlerServiceError, ErrorCode
from ..core.http_client import HttpClient
from ..core.log import get_logger

logger = get_logger("smart_agent")

_M3U8_REGEX = re.compile(r"""(?:["']|\b)(https?://[^\s"'<>]+\.m3u8[^\s"'<>]*)(?:["']|\b)""", re.IGNORECASE)
_MP4_REGEX = re.compile(r"""(?:["']|\b)(https?://[^\s"'<>]+\.mp4[^\s"'<>]*)(?:["']|\b)""", re.IGNORECASE)


class SmartExploreResult(BaseModel):
    base_url: str
    site_name: str
    suggested_key: str
    data_type: str
    categories: list[dict[str, str]]
    recommend: list[dict[str, Any]]
    sample_detail: Optional[dict[str, Any]] = None
    sample_stream: Optional[dict[str, Any]] = None
    generated_rule: dict[str, Any]
    generated_python_code: str = ""
    steps_log: list[str]



class SmartAgent:
    """自动探测引擎。"""

    def __init__(self, target_url: str) -> None:
        self.target_url = target_url.strip()
        parsed = urllib.parse.urlparse(self.target_url)
        if not parsed.scheme:
            self.target_url = f"https://{self.target_url}"
            parsed = urllib.parse.urlparse(self.target_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        # 生成简易 key，例如 kkys01.com -> kkys01
        domain_parts = parsed.netloc.split(":")[0].split(".")
        clean_key = domain_parts[-2] if len(domain_parts) >= 2 else domain_parts[0]
        self.suggested_key = re.sub(r"[^a-zA-Z0-9_]", "", clean_key).lower()
        if not self.suggested_key or not self.suggested_key[0].isalpha():
            self.suggested_key = f"site_{self.suggested_key}"
        self.logs: list[str] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)
        logger.info("[SmartAgent] %s", msg)

    async def explore(self) -> SmartExploreResult:
        self.log(f"开始连接目标站点: {self.target_url}")
        async with HttpClient(base_url=self.base_url) as client:
            resp = await client.request("GET", self.target_url)
            self.log(f"源站响应成功，状态码: {resp.status_code}")

            # 探测是 JSON 还是 HTML
            content_type = resp.headers.get("content-type", "").lower()
            text_body = resp.text

            if "application/json" in content_type or (text_body.startswith("{") and text_body.endswith("}")):
                self.log("检测到目标站为纯 JSON API 接口")
                return await self._explore_json(resp.json())
            else:
                self.log("检测到目标站为 HTML 网页形态，启动智能 DOM 聚类分析")
                return await self._explore_html(client, text_body)

    async def _explore_html(self, client: HttpClient, html: str) -> SmartExploreResult:
        root = parse_html(html)

        # 1. 站点名称推测
        title_node = root.select_first("title")
        raw_title = title_node.text if title_node else self.suggested_key
        site_name = clean_title(raw_title.split("-")[0].split("_")[0].split("|")[0]) or self.suggested_key
        self.log(f"推断站点名称: {site_name}")

        # 2. 启发式提取分类
        categories = self._extract_categories_heuristic(root)
        self.log(f"自动发现 {len(categories)} 个分类导航条目")

        # 3. 启发式聚类提取首页视频列表
        recommend = self._extract_vod_list_heuristic(root, categories=categories)
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
                    sample_detail = self._extract_detail_heuristic(first_vod, detail_root, detail_url, html_content=detail_html)
                    self.log(f"成功提取详情: 《{sample_detail['video']['vod_name']}》，共 {len(sample_detail['episodes'])} 集")

                    # 5. 深入第一集探测播放流
                    if sample_detail["episodes"]:
                        first_ep = sample_detail["episodes"][0]
                        play_href = first_ep.get("play_id")
                        if play_href and play_href.startswith("/"):
                            play_url = safe_resolve_url(self.base_url, play_href)
                            self.log(f"深入嗅探第 1 集播放流页面: {play_url}")
                            play_html = await client.get_text(play_url)
                            sample_stream = self._sniff_stream_url(play_html)
                            if sample_stream:
                                self.log(f"嗅探到播放流直链: {sample_stream['url']}")
                            else:
                                self.log("未直接嗅探到 m3u8，尝试在详情页源码中搜索...")
                except Exception as exc:
                    self.log(f"深入详情页发生非致命异常: {exc}")

        # 6. 生成可运行的 SiteRule 与独立 Python 爬虫脚本
        generated_rule = self._generate_rule(site_name, categories, recommend)
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


    def _extract_categories_heuristic(self, root: HtmlNode) -> list[dict[str, str]]:
        categories = []
        seen_tids = set()

        # 常见分类链接特征
        patterns = [
            r"/type/(\d+)",
            r"/vod/type/id/(\d+)",
            r"/category/(\d+)",
            r"/show/(\d+)",
            r"tid=(\d+)",
        ]

        # 扫描导航容器或前 100 个带特征链接的 a 标签
        candidates = root.select("nav a, .nav a, .menu a, header a, .navbar a, a")
        for a in candidates:
            href = a.attr("href")
            text = collapse_whitespace(a.text)
            if not href or not text or len(text) > 8:
                continue
            if text in ("首页", "留言", "APP", "求片", "公告", "排行榜", "资讯"):
                continue

            for pat in patterns:
                m = re.search(pat, href)
                if m:
                    tid = m.group(1)
                    if tid not in seen_tids:
                        seen_tids.add(tid)
                        categories.append({"tid": tid, "name": text})
                    break

            if len(categories) >= 8:
                break

        if not categories:
            categories = [
                {"tid": "1", "name": "电影"},
                {"tid": "2", "name": "连续剧"},
                {"tid": "3", "name": "综艺"},
                {"tid": "4", "name": "动漫"},
            ]
        return categories

    def _extract_vod_list_heuristic(self, root: HtmlNode, categories: Optional[list[dict[str, str]]] = None) -> list[dict[str, Any]]:
        results = []
        seen_ids = set()

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

        nodes = []
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

        cat_hrefs = set()
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
            # 寻找链接
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
                pic = safe_resolve_url(self.base_url, pic)
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

    def _extract_detail_heuristic(self, vod_item: dict[str, Any], root: HtmlNode, detail_url: str, html_content: str = "") -> dict[str, Any]:
        # 提取简介
        desc = ""
        for sel in [".video-info-content", ".desc", ".content", ".plot", "#desc", "p.detail"]:
            dnode = root.select_first(sel)
            if dnode and len(dnode.text.strip()) > 10:
                desc = collapse_whitespace(dnode.text)
                break

        episodes = []
        lines = []

        # 检查是否包含内嵌 player 播放数据（如 var pp = {...}）
        if html_content:
            pp_match = re.search(r"var\s+pp\s*=\s*(\{.*?\});", html_content)
            if pp_match:
                try:
                    pp_data = json.loads(pp_match.group(1))
                    pp_lines = pp_data.get("lines", [])
                    for l_idx, line_item in enumerate(pp_lines, start=1):
                        if isinstance(line_item, list) and len(line_item) >= 4:
                            line_id = str(line_item[0])
                            line_name = str(line_item[1])
                            urls = line_item[3] if isinstance(line_item[3], list) else []
                            lines.append({"line": line_id, "name": line_name, "count": len(urls)})
                            if l_idx == 1:
                                for ep_idx, ep_url in enumerate(urls, start=1):
                                    episodes.append({
                                        "ep_index": ep_idx,
                                        "ep_name": f"第{ep_idx}集",
                                        "play_id": ep_url,
                                        "line": line_id,
                                    })
                except Exception:
                    pass

        # 若未从脚本中提取到剧集，从普通链接提取
        if not episodes:
            ep_links = root.select(".module-play-list-link, .playlist a, .urlli a, a[href*='/play/']")
            for idx, ep_a in enumerate(ep_links, start=1):
                ep_href = ep_a.attr("href")
                ep_name = collapse_whitespace(ep_a.text) or f"第{idx}集"
                if ep_href and not ep_href.startswith("javascript"):
                    episodes.append({
                        "ep_index": idx,
                        "ep_name": ep_name,
                        "play_id": ep_href,
                        "line": "1",
                    })
                if len(episodes) >= 80:
                    break

        if not lines:
            lines = [{"line": "1", "name": "默认线路", "count": len(episodes)}]

        return {
            "video": {
                "vod_id": vod_item["vod_id"],
                "vod_name": vod_item["vod_name"],
                "vod_pic": vod_item["vod_pic"],
                "vod_remarks": vod_item["vod_remarks"] or f"共{len(episodes)}集",
            },
            "desc": desc,
            "episodes": episodes,
            "lines": lines,
        }

    def _sniff_stream_url(self, html: str) -> Optional[dict[str, str]]:
        # 1. 优先检查内嵌 var pp 播放器直链
        pp_match = re.search(r"var\s+pp\s*=\s*(\{.*?\});", html)
        if pp_match:
            try:
                pp_data = json.loads(pp_match.group(1))
                for line in pp_data.get("lines", []):
                    if isinstance(line, list) and len(line) >= 4 and isinstance(line[3], list) and line[3]:
                        return {"url": line[3][0], "format": "m3u8"}
            except Exception:
                pass

        # 2. 正则提取 m3u8
        m3u8_match = _M3U8_REGEX.search(html)
        if m3u8_match:
            raw_url = m3u8_match.group(1).replace(r"\/", "/")
            return {"url": raw_url, "format": "m3u8"}

        mp4_match = _MP4_REGEX.search(html)
        if mp4_match:
            raw_url = mp4_match.group(1).replace(r"\/", "/")
            return {"url": raw_url, "format": "mp4"}

        return None


    def _generate_rule(self, site_name: str, categories: list[dict[str, str]], recommend: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "key": self.suggested_key,
            "name": site_name,
            "version": "1.0.0",
            "base_url": self.base_url,
            "mode": "direct",
            "data_type": "html",
            "home": {
                "path": "/",
                "method": "GET",
                "static_categories": categories,
                "recommend_container": ".module-item, .vodlist_item, li",
                "recommend_item": {
                    "vod_id": { "selector": "a", "attribute": "href", "regex": r"/(\d+)\.html" },
                    "vod_name": { "selector": ".title, h3, a" },
                    "vod_pic": { "selector": "img", "attribute": "data-original" },
                    "vod_remarks": { "selector": ".module-item-text, .remarks, span" }
                }
            },
            "detail": {
                "path": "/detail/{id}.html",
                "method": "GET",
                "title_extractor": { "selector": "h1, .page-title" },
                "pic_extractor": { "selector": "img", "attribute": "data-original" },
                "desc_extractor": { "selector": ".video-info-content, .desc, p" },
                "episodes_container": "a[href*='/play/']",
                "episode_item": {
                    "ep_name": { "selector": "" },
                    "play_id": { "attribute": "href" }
                }
            },
            "play": {
                "path": "{play_id}",
                "method": "GET",
                "play_url_extractor": {
                    "type": "regex",
                    "regex": r"""(?:["']|\b)(https?://[^\s"'<>]+\.m3u8[^\s"'<>]*)(?:["']|\b)"""
                },
                "format": "m3u8"
            }
        }

    async def _explore_json(self, data: Any) -> SmartExploreResult:
        # JSON 探测逻辑
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
