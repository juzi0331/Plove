#!/usr/bin/env python
"""黄果短剧官网（https://huangguoai.com）单文件爬虫适配器。

站点特征（2026-10 实测，非推测）：

* 全站服务端渲染，裸 GET 直接 200；无反爬闸门、无 CDndefend、无限速迹象；
* 频道页 ``/ai-duanju/`` 等，分页 ``/ai-duanju/<页码>/``（第 1 页无页码段）；
  ``nav.hg-pager`` 里的页码链接上限就是总页数；
* 卡片 ``div.hg-drama-card``：封面在 ``img[data-src]``（``src`` 是占位图），
  标题在 ``.hg-drama-card__title`` 锚点的**直接文本**（内含 ``.sr-only``
  隐藏水印"全集在线观看"，取后代 text 会混入，必须只取直接文本），
  备注在 ``.hg-drama-card__episode`` 的 ``data-ep-base``（如"更新至9集"）；
* 首页的 ``hg-search-suggest``（热搜词）里埋了同款卡片、hero 大图
  ``a.hg-hero__cover-link`` 指向站外广告 —— 都要按祖先特征过滤掉；
* 详情页 ``/video/<id>/``、第 N 集 ``/video/<id>/ep-N/``（第 1 集即详情页
  本身），页面内嵌 ``<script id="videoInitialData" type="application/json">``：
  ``videoSrc`` 是**明文 m3u8**（HLS 自带 AES-128 密钥段，密钥/IV 由播放器
  按清单自理，爬虫不需要碰）；``videoApi/videoKey/videoIv`` 实测为空；
* ``epPlaySrcs`` 的键是**集号**（当前集 ±1 的地址窗口，已实测确认：
  ep2 页的 ``"2"`` 与该页 ``videoSrc`` 逐字符一致，且 auth_key 每页现签）
  —— 所以 play 必须落到对应集的页面现取，地址不可缓存；
* 选集列表 ``a.hg-web-play__ep[data-ep-id]``，第 1 集的 href 是规范地址
  ``/video/<id>/``，其余是 ``/video/<id>/ep-N/``；
* 播放只有一条线路（epPlaySrcs 的键是集号不是线路），lines 固定 1 条；
* 无效 id / 越界页码 / 不存在的标签都返回 HTTP 404。

用法::

    python sites/huangguoai.py meta
    python sites/huangguoai.py home
    python sites/huangguoai.py category --tid ai-duanju --page 2
    python sites/huangguoai.py detail --id 7420
    python sites/huangguoai.py play --id 7420 --ep 2
    # 带上详情里给的 play_id 可精确落集（可省一次集号推断）
    python sites/huangguoai.py play --play-id /video/7420/ep-2/
"""

from __future__ import annotations

import json
import os
import re
import sys

if __package__ in (None, ""):  # 允许直接 `python sites/huangguoai.py` 运行
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import Client, CrawlerError, clean, cli, log, parse  # noqa: E402

KEY = "huangguoai"
NAME = "黄果短剧官网"
BASE_URL = "https://huangguoai.com/"
DEFAULT_TIMEOUT = 20.0

#: 卡片/详情共用的影片路径：``/video/<id>/``
_DETAIL_HREF_RE = re.compile(r"/video/(\d+)/")

#: 顶栏/侧栏里真正可当"分类"用的导航：AI 频道 + 排行榜
_CATEGORY_HREF_RE = re.compile(r"^/(ai-[\w-]+|ranks/hot)/$")

#: 集页定位符（play_id）：``/video/<id>/`` 或 ``/video/<id>/ep-<n>/``
_EP_HREF_RE = re.compile(r"^/video/(\d+)/(?:ep-(\d+)/)?$")

#: 详情/集页内嵌的 JSON 信令块
_INITIAL_DATA_RE = re.compile(
    r'<script id="videoInitialData"[^>]*>(.*?)</script>', re.S
)

#: 分类 tid 的合法形态（含 ranks/hot 这类带一段目录的）
_TID_RE = re.compile(r"[\w-]+(?:/[\w-]+)*")


# ------------------------------------------------------------------ 工具

def _direct_text(node) -> str:
    """只取节点的**直接**文本子节点。

    站点把水印（``.sr-only``）藏在标题锚点内部，取全部后代 text 会把
    "全集在线观看"之类的水印一起带进来，所以标题只能取直接文本。
    """
    if node is None:
        return ""
    chunks = [child.data or "" for child in node.children if child.is_text]
    return clean.collapse("".join(chunks))


def _in_noise(node) -> bool:
    """卡片是否躺在不可信的容器里。

    三类噪音：首页热搜词块（``hg-search-suggest``）、分类页隐藏面板
    （带 ``hidden`` 属性或行内隐藏）、翻版卡片模板（``<template>``）。
    """
    parent = node.parent
    while parent is not None:
        if parent.tag == "template" or "hidden" in parent.attrs or parent.is_hidden:
            return True
        classes = parent.attrs.get("class") or ""
        if "hg-search-suggest" in classes:
            return True
        parent = parent.parent
    return False


def _initial_data(html: str) -> dict:
    """解析详情/集页内嵌的 ``videoInitialData`` JSON 信令。"""
    match = _INITIAL_DATA_RE.search(html or "")
    if not match:
        return {}
    try:
        payload = json.loads(match.group(1))
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _year(value) -> int:
    text = str(value or "")
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else 0


# ------------------------------------------------------------------ 映射层

def _card(node):
    """``div.hg-drama-card`` -> VodItem。缺名字的一律丢弃，不伪造。"""
    link = node.select_first("a.hg-drama-card__cover-link")
    if link is None:
        link = node.select_first('a[href^="/video/"]')
    if link is None:
        return None
    match = _DETAIL_HREF_RE.search(link.attr("href") or "")
    if not match:
        return None

    name = ""
    title = node.select_first(".hg-drama-card__title")
    if title is not None:
        name = _direct_text(title.select_first("a") or title)
        if not name:
            name = clean.strip_promo(title.text)
    if not name:
        image = link.select_first("img")
        name = clean.strip_promo(image.attr("alt") or "") if image is not None else ""
    if not name:
        return None

    video = {
        "vod_id": match.group(1),
        "vod_name": name,
        "vod_pic": clean.absolute(parse.first_image(link), BASE_URL),
        "vod_remarks": "",
    }

    episode = node.select_first(".hg-drama-card__episode")
    if episode is not None:
        remarks = clean.collapse(episode.attr("data-ep-base") or "") or episode.text
        video["vod_remarks"] = clean.strip_promo(remarks)

    score = clean.to_float(node.select_first(".hg-drama-card__score").text) \
        if node.select_first(".hg-drama-card__score") is not None else None
    if score:
        video["vod_score"] = score

    tags = [
        _direct_text(tag)
        for tag in node.select(".hg-drama-card__tags a.hg-tag")
    ]
    tags = [tag for tag in tags if tag]
    if tags:
        video["vod_type"] = ",".join(tags)
    return video


def _cards(root):
    out = []
    for node in root.select("div.hg-drama-card"):
        if _in_noise(node):
            continue
        card = _card(node)
        if card is not None:
            out.append(card)
    return clean.dedupe(out, key=lambda item: item["vod_id"])


def _category_items(root):
    """首页"分类推荐"栏的 ``a.hg-category-item`` -> VodItem（补充推荐）。"""
    out = []
    for anchor in root.select("a.hg-category-item"):
        if _in_noise(anchor):
            continue
        match = _DETAIL_HREF_RE.search(anchor.attr("href") or "")
        if not match:
            continue
        name = _direct_text(anchor.select_first(".hg-category-item__title"))
        if not name:
            continue
        out.append(
            {
                "vod_id": match.group(1),
                "vod_name": name,
                "vod_pic": clean.absolute(parse.first_image(anchor), BASE_URL),
                "vod_remarks": "",
            }
        )
    return out


def _categories(root):
    """顶栏 + 侧栏导航 -> categories。只收 AI 频道与排行榜。

    注意：``/topics/``（专题拼盘）、``/chigua/``（社区）、``/go-home/``
    （APP 下载）和站外 APP 链接都不是影片分类，必须排除。
    """
    out = []
    seen = set()
    for css in (".hg-topbar-nav__item", ".hg-nav-item"):
        for anchor in root.select(css):
            match = _CATEGORY_HREF_RE.match(anchor.attr("href") or "")
            if not match:
                continue
            tid = match.group(1)
            if tid in seen:
                continue
            name = clean.collapse(anchor.text)
            if not name:
                continue
            seen.add(tid)
            out.append({"tid": tid, "name": name})
    return out


def _has_more(root, tid: str, page: int) -> bool:
    """``nav.hg-pager`` 页码链接里的最大页数 > 当前页即还有下一页。"""
    best = 0
    for anchor in root.select("a.hg-pager__page"):
        matched = re.fullmatch(
            r"/" + re.escape(tid) + r"/(\d+)/", anchor.attr("href") or ""
        )
        if matched:
            best = max(best, int(matched.group(1)))
    return best > page


def _episodes(root, vid: str, fallback_ep: int = 1):
    """选集锚点 -> episodes（ep_index 1 起算，play_id 是站内相对路径）。"""
    out = []
    for anchor in root.select("a.hg-web-play__ep"):
        index = clean.to_int(anchor.attr("data-ep-id"))
        href = clean.safe_relative_path(anchor.attr("href") or "")
        if index is None or not href:
            continue
        out.append(
            {
                "ep_index": index,
                "ep_name": f"第{index}集",
                "play_id": href,
                "line": 1,
            }
        )
    out.sort(key=lambda item: item["ep_index"])
    out = clean.dedupe(out, key=lambda item: item["ep_index"])
    if not out:
        # 单集剧可能不渲染选集列表：至少保住信令里声明的当前集
        out = [
            {
                "ep_index": fallback_ep,
                "ep_name": f"第{fallback_ep}集",
                "play_id": f"/video/{vid}/" if fallback_ep <= 1 else f"/video/{vid}/ep-{fallback_ep}/",
                "line": 1,
            }
        ]
    return out


# --------------------------------------------------------------------- 站点

class Huangguoai:
    key = KEY
    name = NAME
    version = "1.0.0"
    base_url = BASE_URL
    #: 直连源站即可播放（清单 CORS 开放，实测无 Referer 也能 200）
    mode = "direct"
    capabilities = ("meta", "home", "category", "detail", "play")

    def __init__(self, client=None):
        self.http = client or Client(
            base_url=BASE_URL,
            timeout=DEFAULT_TIMEOUT,
            retries=1,
            headers={
                "Referer": BASE_URL,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )

    # ---------------------------------------------------------------- 基础

    def _page(self, path: str) -> str:
        response = self.http.get(path)
        if response.status == 404:
            raise CrawlerError("NOT_FOUND", f"页面不存在: {path}")
        if not response.ok:
            raise CrawlerError("HTTP_ERROR", f"{path} 返回 HTTP {response.status}")
        return response.text

    @staticmethod
    def _check_id(id) -> str:
        value = str(id or "").strip()
        if not re.fullmatch(r"\d{1,12}", value):
            raise CrawlerError("NOT_FOUND", f"无效的影片 id: {id}")
        return value

    @staticmethod
    def _check_tid(tid) -> str:
        value = str(tid or "").strip().strip("/")
        if not value or ".." in value or not _TID_RE.fullmatch(value):
            raise CrawlerError("NOT_FOUND", f"无效的分类 id: {tid}")
        return value

    # ---------------------------------------------------------------- 动作

    def meta(self):
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "mode": self.mode,
            "capabilities": list(self.capabilities),
            "play_format": ["m3u8"],
            "note": (
                "SSR 站点；频道 /<tid>/、分页 /<tid>/<页>/；详情 /video/<id>/、"
                "选集 /video/<id>/ep-<n>/；m3u8 明文写在 videoInitialData 里，"
                "epPlaySrcs 键是集号（±1 窗口），地址现签、不可缓存"
            ),
        }

    def home(self):
        root = parse.parse_html(self._page("/"))
        recommend = _cards(root) + _category_items(root)
        return {
            "categories": _categories(root),
            "recommend": clean.dedupe(recommend, key=lambda item: item["vod_id"]),
        }

    def category(self, tid, page=1):
        tid = self._check_tid(tid)
        page = clean.to_int(page, 1) or 1
        if page < 1:
            page = 1
        path = f"/{tid}/" if page <= 1 else f"/{tid}/{page}/"
        root = parse.parse_html(self._page(path))
        return {
            "videos": _cards(root),
            "page": page,
            "has_more": _has_more(root, tid, page),
        }

    def detail(self, id):
        vid = self._check_id(id)
        html = self._page(f"/video/{vid}/")
        data = _initial_data(html)

        name = clean.strip_promo(data.get("title") or "")
        if not name:
            # 信令缺失时退回 <h1>（正常情况下信令一定在）
            root = parse.parse_html(html)
            heading = root.select_first("h1")
            name = clean.strip_promo(heading.text) if heading is not None else ""
        if not name:
            raise CrawlerError("PARSE_ERROR", f"详情页未解析到影片: {vid}")

        current_ep = clean.to_int(data.get("ep"), 1) or 1
        root = parse.parse_html(html)
        episodes = _episodes(root, vid, fallback_ep=current_ep)

        video = {
            "vod_id": str(clean.to_int(data.get("id"), vid) or vid),
            "vod_name": name,
            "vod_pic": clean.absolute(
                data.get("coverSrc") or data.get("posterSrc") or "", BASE_URL
            ),
            "vod_remarks": f"更新至{len(episodes)}集" if len(episodes) > 1 else "",
        }
        tags = [clean.clean_text(tag) for tag in data.get("tags") or []]
        tags = [tag for tag in tags if tag]
        if tags:
            video["vod_type"] = ",".join(tags)
        year = _year(data.get("time"))
        if year:
            video["vod_year"] = year

        return {
            "video": video,
            "desc": clean.strip_promo(data.get("description") or ""),
            "episodes": episodes,
            # 该源单线路：epPlaySrcs 的键是集号（±1 窗口），不是线路
            "lines": [{"line": 1, "name": "默认线路", "count": len(episodes)}],
        }

    def play(self, id=None, ep=1, line=1, play_id=None):
        line_no = clean.to_int(line, 1) or 1
        if line_no > 1:
            log.warn(f"该源只有一条线路，忽略 --line {line_no}")
        index = clean.to_int(ep, 1) or 1
        if index < 1:
            index = 1

        # play_id 加速通道：必须是本站的集页相对路径，且（若给了 id）归属一致
        path = clean.safe_relative_path(play_id)
        embedded_ep = None
        if path:
            matched = _EP_HREF_RE.match(path)
            if not matched:
                log.warn(f"忽略不可信的 play_id（不是集页路径）: {str(play_id)[:80]!r}")
                path = ""
            else:
                vid = self._check_id(id) if id is not None else matched.group(1)
                if matched.group(1) != vid:
                    log.warn(
                        f"play_id 与 --id 不一致，按 --id 处理: "
                        f"{matched.group(1)} != {vid}"
                    )
                    path = ""
                else:
                    embedded_ep = clean.to_int(matched.group(2), 1) or 1
        else:
            vid = self._check_id(id)

        if not path and id is None:
            raise CrawlerError("NOT_FOUND", "play 需要 --id；或者传一个合法的 --play-id")

        # play_id 自带的集号优先于 --ep（它是详情里下发的精确定位符）
        target_ep = embedded_ep or index
        if not path:
            path = f"/video/{vid}/" if target_ep <= 1 else f"/video/{vid}/ep-{target_ep}/"

        html = self._page(path)
        data = _initial_data(html)
        if not data:
            raise CrawlerError("PARSE_ERROR", f"集页缺少 videoInitialData: {path}")

        page_ep = clean.to_int(data.get("ep"), target_ep) or target_ep
        if page_ep != target_ep:
            log.warn(f"站点返回第 {page_ep} 集（请求第 {target_ep} 集）: {path}")

        sources = data.get("epPlaySrcs") or {}
        url = str(sources.get(str(page_ep)) or data.get("videoSrc") or "").strip()
        if not url:
            raise CrawlerError("PARSE_ERROR", f"第 {page_ep} 集没有播放地址")

        suffix = url.split("?", 1)[0].split("#", 1)[0].lower()
        fmt = "mp4" if suffix.endswith(".mp4") else "m3u8"
        return {"url": url, "format": fmt, "headers": {"Referer": BASE_URL}}


if __name__ == "__main__":
    cli.main(Huangguoai())
