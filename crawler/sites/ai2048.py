#!/usr/bin/env python
"""2048ai.vip 短剧站适配器。

站点特征（实测）：

* 纯 SPA + **标准 REST JSON API**，不用解析一行 HTML；
* 详情接口的 ``episodes[].videoUrl`` 是相对路径（``jpd/...m3u8``）；
* 播放要经站点自己的代理：``/api/v1/m3u8/proxy?path=<urlencoded videoUrl>``，
  代理返回的清单里，分片是带 ``auth_key`` 的限时签名地址（CDN 动态域名）。
  所以 ``mode`` 是 ``direct`` —— 不需要我们自己做流代理，但地址必须每次现取。

命名注意：文件名不能叫 ``2048ai.py``（数字开头不是合法模块名），故用 ``ai2048``。

用法::

    python sites/ai2048.py meta
    python sites/ai2048.py home
    python sites/ai2048.py category --tid 27 --page 1
    python sites/ai2048.py detail --id 249
    python sites/ai2048.py play --id 249 --ep 1
    python sites/ai2048.py selftest
"""

from __future__ import annotations

import os
import sys
import urllib.parse

if __package__ in (None, ""):  # 允许直接 `python sites/ai2048.py` 运行
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import Client, CrawlerError, clean, cli, log  # noqa: E402

KEY = "ai2048"
NAME = "2048 AI短剧"
BASE_URL = "https://2048ai.vip"
PRODUCT_ID = 1
PAGE_SIZE = 24

#: 首页三个板块的展示名（字段名 -> 中文标题）
HOME_SECTIONS = (
    ("banner", "热播推荐"),
    ("chaseRank", "追剧榜"),
    ("featured", "精选短剧"),
)


class Ai2048:
    key = KEY
    name = NAME
    version = "1.0.0"
    base_url = BASE_URL
    #: 该站播放时是直连源站，还是必须走后端代理
    mode = "direct"
    #: 能力清单：后端据此路由，不支持的命令必须明确报错
    capabilities = ("meta", "home", "category", "detail", "play", "selftest")

    def __init__(self, client=None):
        self.http = client or Client(
            base_url=BASE_URL,
            timeout=10.0,
            retries=2,
            headers={
                "Referer": BASE_URL + "/",
                "Accept": "application/json, text/plain, */*",
            },
        )

    # ------------------------------------------------------------ 基础设施

    def _api(self, path, **params):
        """调用 ``/api/v1/*``，拆掉 ``{code, message, data}`` 外壳。"""
        params.setdefault("productId", PRODUCT_ID)
        response = self.http.get("/api/v1" + path, params=params)

        if response.status == 403 or response.status == 451:
            raise CrawlerError("BLOCKED", f"{path} 被拦截 (HTTP {response.status})")
        if not response.ok:
            raise CrawlerError("HTTP_ERROR", f"{path} 返回 HTTP {response.status}")

        payload = response.json()
        if not isinstance(payload, dict):
            raise CrawlerError("PARSE_ERROR", f"{path} 响应不是对象")
        if payload.get("code") != 200:
            raise CrawlerError(
                "HTTP_ERROR",
                f"{path} 业务码 {payload.get('code')}: {payload.get('message')}",
            )
        return payload.get("data")

    # ---------------------------------------------------------------- 命令

    def meta(self):
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "mode": self.mode,
            "capabilities": list(self.capabilities),
            "play_format": ["m3u8"],
        }

    def home(self):
        data = self._api("/short-dramas/home") or {}
        categories = self._categories()
        sections = []
        recommend = []
        seen_ids: set[str] = set()

        def take_unseen(items, limit=10):
            picked = []
            for video in _to_vod_list(items):
                vid = str(video["vod_id"])
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)
                picked.append(video)
                recommend.append(video)
                if len(picked) >= limit:
                    break
            return picked

        # 源站三个首页字段实测会大量重复。跨板块去重，避免用户看到
        # “热播 / 追剧榜 / 精选”其实是同一排内容。
        for field, title in HOME_SECTIONS:
            videos = take_unseen(data.get(field))
            if videos:
                sections.append({"title": title, "videos": videos})

        # 如果源站首页字段重复得只剩很少内容，用真实分类补足不同楼层。
        # 最多尝试 6 个分类，避免为了首页无限追加上游请求。
        if len(sections) < 3 or sum(len(s["videos"]) for s in sections) < 20:
            for category in categories[:6]:
                if len(sections) >= 4:
                    break
                listing = self._api(
                    "/short-dramas",
                    sortBy="heat",
                    page=1,
                    size=12,
                    categoryId=category["tid"],
                ) or {}
                videos = take_unseen(listing.get("items"))
                if len(videos) < 3:
                    continue
                sections.append(
                    {
                        "title": category["name"],
                        "tid": category["tid"],
                        "videos": videos,
                    }
                )

        return {
            "categories": categories,
            "recommend": recommend,
            "sections": sections,
        }

    def category(self, tid=None, page=1):
        params = {"sortBy": "heat", "page": page, "size": PAGE_SIZE}
        if tid is not None and str(tid).strip() != "":
            params["categoryId"] = tid

        data = self._api("/short-dramas", **params) or {}
        videos = _to_vod_list(data.get("items"))
        current = clean.to_int(data.get("page"), page)
        total_pages = clean.to_int(data.get("totalPages"), 1)
        return {
            "videos": videos,
            "page": current,
            "has_more": bool(current and total_pages and current < total_pages),
        }

    def search(self, kw=None, page=1):
        # 能力清单里没有 search：宁可明确报错，也不要返回空列表装作搜过了
        raise CrawlerError("UNSUPPORTED", "该源暂未提供搜索接口，能力清单中已标注")

    def detail(self, id):
        data = self._api(f"/short-dramas/{id}")
        if not isinstance(data, dict) or data.get("id") is None:
            raise CrawlerError("NOT_FOUND", f"短剧不存在: {id}")

        video = _to_vod(data)
        if video is None:
            raise CrawlerError("PARSE_ERROR", f"详情缺少必填字段: {id}")

        episodes = []
        for raw in data.get("episodes") or []:
            if not isinstance(raw, dict):
                continue
            index = clean.to_int(raw.get("episodeNo"))
            if index is None:
                continue
            episodes.append(
                {
                    # 约定 ep_index 为 **1 起算** 的集号
                    "ep_index": index,
                    "ep_name": clean.strip_promo(raw.get("title"))
                    or f"第{index}集",
                    "play_id": str(raw.get("videoId") or ""),
                    "duration_sec": clean.to_int(raw.get("durationSec")),
                }
            )
        episodes.sort(key=lambda item: item["ep_index"])

        return {
            "video": video,
            "desc": clean.strip_promo(data.get("description")),
            "episodes": episodes,
        }

    def play(self, id, ep=1):
        index = clean.to_int(ep, 1) or 1
        data = self._api(f"/short-dramas/{id}")
        if not isinstance(data, dict):
            raise CrawlerError("NOT_FOUND", f"短剧不存在: {id}")

        raw = _pick_episode(data, index)
        if raw is None:
            total = len(data.get("episodes") or [])
            raise CrawlerError("NOT_FOUND", f"第 {index} 集不存在（共 {total} 集）")

        path = str(raw.get("videoUrl") or "").strip()
        if not path:
            raise CrawlerError("PARSE_ERROR", f"第 {index} 集没有 videoUrl")

        # 站点自己的 m3u8 代理；分片的 auth_key 由代理现签，所以地址不可缓存
        url = f"{BASE_URL}/api/v1/m3u8/proxy?path={urllib.parse.quote(path, safe='')}"
        return {"url": url, "format": "m3u8", "headers": {}}

    def selftest(self):
        """结构指纹：命中数骤降就说明接口结构变了，应触发熔断。"""
        listing = self._api("/short-dramas", sortBy="heat", page=1, size=1) or {}
        home = self._api("/short-dramas/home") or {}
        items = listing.get("items") or []
        return {
            "selectors": {
                "list.items": len(items),
                "list.total": clean.to_int(listing.get("total"), 0),
                "home.banner": len(home.get("banner") or []),
                "home.featured": len(home.get("featured") or []),
                "home.chaseRank": len(home.get("chaseRank") or []),
                "categories": len(self._categories()),
            }
        }

    # ------------------------------------------------------------ 内部工具

    def _categories(self):
        data = self._api("/categories", type="video") or []
        out = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            if raw.get("enabled") is False:
                continue
            product = raw.get("productId")
            if product is not None and clean.to_int(product) != PRODUCT_ID:
                continue
            tid = clean.to_int(raw.get("id"))
            if tid is None:
                continue
            out.append({"tid": str(tid), "name": clean.clean_text(raw.get("name"))})
        return out


# ------------------------------------------------------------------ 映射层


def _looks_like_vod(raw) -> bool:
    return isinstance(raw, dict) and raw.get("id") is not None and (
        "title" in raw or "coverUrl" in raw
    )


def _to_vod_list(items):
    out = []
    for raw in items or []:
        video = _to_vod(raw)
        if video is not None:
            out.append(video)
    return out


def _to_vod(raw):
    """转成全站统一的 VodItem。缺必填字段的一律丢弃，不伪造。"""
    if not _looks_like_vod(raw):
        return None
    name = clean.strip_promo(raw.get("title"))
    if not name:
        return None

    video = {
        "vod_id": str(raw.get("id")),
        "vod_name": name,
        "vod_pic": clean.absolute(raw.get("coverUrl") or "", BASE_URL),
        "vod_remarks": _remarks(raw),
    }

    year = _year(raw.get("publishedAt"))
    if year:
        video["vod_year"] = year

    score = clean.to_float(raw.get("rating"))
    if score:
        video["vod_score"] = score

    tags = _tags(raw.get("tags"))
    if tags:
        video["vod_type"] = ",".join(tags)

    return video


def _remarks(raw) -> str:
    count = clean.to_int(raw.get("episodeCount"))
    if count:
        return f"全{count}集"
    return ""


def _year(value):
    if not value:
        return 0
    text = str(value)
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return 0


def _tags(value):
    """``tags`` 实测形状不固定，可能是字符串、字符串数组或对象数组。"""
    if not value:
        return []
    if isinstance(value, str):
        return [clean.clean_text(part) for part in value.split(",") if part.strip()]
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                text = clean.clean_text(item)
            elif isinstance(item, dict):
                text = clean.clean_text(item.get("name") or item.get("label") or "")
            else:
                text = ""
            if text:
                out.append(text)
        return out
    return []


def _pick_episode(data, index):
    for raw in data.get("episodes") or []:
        if isinstance(raw, dict) and clean.to_int(raw.get("episodeNo")) == index:
            return raw
    return None


if __name__ == "__main__":
    cli.main(Ai2048())
