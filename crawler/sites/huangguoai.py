#!/usr/bin/env python
"""黄果短剧官网（https://huangguoai.com）单文件采集器 / 适配器。

站点形态（2026-10-01 实测，非推测，抓样见文末「实测记录」）
----------------------------------------------------------
* 全站服务端渲染，裸 GET 直接 200；无反爬闸门、无 CDN 挑战、无限速迹象。
* 频道页 ``/ai-duanju/`` ``/ai-manju/`` ``/ai-huanlian/`` ``/ai-mogai/``、
  榜单 ``/ranks/hot/``（单页不分页）；页码段是 ``/<tid>/<页>/``，
  而**题材标签页是** ``/tag/<slug>/page/<页>/``（两种格式不同，别写死一种）。
  总页数直接写在分页条上：``.hg-pager__jump[data-pages]``。
* 榜单 ``/ranks/hot/`` 是**单页**（没有分页条，``has_more`` 恒 false），而且用的是
  **行式卡片** ``div.hg-rank-item``（``.hg-rank-item__title`` ``__tags`` ``__heat-value``），
  跟列表页的 ``div.hg-drama-card`` 不是一套标记 —— 两种都要解析。
* 卡片 ``div.hg-drama-card``：封面在 ``img[data-src]``（``src`` 是占位图），
  标题在 ``.hg-drama-card__title`` 锚点的**直接文本**（锚点内部的
  ``span.sr-only`` 是水印「全集在线观看」，取后代 text 会混进标题），
  备注在 ``.hg-drama-card__episode[data-ep-base]``（如「更新至9集」），
  题材标签在 ``.hg-drama-card__tags a.hg-tag``（同样带 sr-only 水印）。
* 首页噪音三处，必须滤掉，否则会抓回广告：hero 大图
  ``a.hg-hero__cover-link`` 指向站外（``rel="sponsored"``）；搜索建议面板
  ``#hg-search-suggest`` 里埋了同款卡片但整块隐藏；另有 ``<template>`` 翻版卡片。
* 详情页 ``/video/<id>/``、第 N 集 ``/video/<id>/ep-<n>/``（第 1 集就是详情页本身，
  ``/video/<id>/ep-1/`` 会 301 回详情页）。页面内嵌
  ``<script id="videoInitialData" type="application/json">``：
  ``videoSrc`` 是**明文 m3u8**（HLS 自带 AES-128，密钥/IV 在清单里，爬虫不用碰）；
  ``videoApi/videoKey/videoIv`` 实测为空。
* ``epPlaySrcs`` 的键是**集号**，且只覆盖当前集 ±1 的窗口 ——
  所以 ``play`` 必须落到目标集的那一页现取；``auth_key`` 是现签的短时效签名，
  **播放地址绝不可缓存**。
* 只有一条播放线路（``epPlaySrcs`` 的键是集号，不是线路号），``lines`` 固定 1 条。
* 站点没有演员/导演/地区字段（只有「上线日期 / 出品 / 更新状态 / 播放次数 /
  单集片长 / 题材类型」）。**不编造**：抓得到就填，抓不到就不给这个键。
* 无效 id、越界页码、不存在的集都返回 HTTP 404（软 404 也有，但状态码是真的）。

契约说明
--------
``detail`` 同时给两种形状，互不冲突、都是真实数据：

* ``lines[].episodes[]`` —— 本文件的主契约（线路内嵌自己的剧集列表）；
* 顶层 ``episodes[]`` —— 本项目后端 ``DetailPayload`` 的形状（平铺 + ``line`` 字段）。

``play_id`` 用 ``<vod_id>|<line>|<ep>`` 复合定位符（详情里下发、上层原样传回），
``play`` 同时接受站内集页相对路径 ``/video/<id>/ep-<n>/``（人工传参）；
两种都解析不出来时**退回** ``(id, line, ep)`` 慢路径，不报错。

用法::

    # 后端热部署会自动注入 CRAWLER_KIT_PATH / PYTHONPATH；本地手跑：
    PYTHONPATH=<repo>/crawler python huangguoai.py meta
    PYTHONPATH=<repo>/crawler python huangguoai.py home
    PYTHONPATH=<repo>/crawler python huangguoai.py category --tid ai-duanju --page 2
    PYTHONPATH=<repo>/crawler python huangguoai.py category --tid tag/dushi
    PYTHONPATH=<repo>/crawler python huangguoai.py detail --id 7420
    PYTHONPATH=<repo>/crawler python huangguoai.py play --id 7420 --ep 2
    PYTHONPATH=<repo>/crawler python huangguoai.py play --play-id '7420|1|2'

实测记录（2026-10-01，真抓，别再凭猜测改选择器）
----------------------------------------------
======================  ==================================================
清单（videoSrc）         HTTP 200、``Access-Control-Allow-Origin: *``、
                        ``Content-Type: text/plain``（内容是 ``#EXTM3U``，
                        媒体清单，分片是绝对地址，无需重写）
AES-128 密钥            HTTP 200、16 字节、CORS ``*``（客户端可直接取）
``.ts`` 分片            **HTTP 403**（``openresty`` / ``Forbid_code=000200``）
                        —— 换 Referer / Origin / Range / 浏览器全套头都不行，
                        而同一台 CDN 上的 ``crypt.key`` 却是 200，
                        所以更像是**出口 IP 被挡**（沙盒出口是机房 IP），
                        不是防盗链缺头。因此 ``mode`` 仍标 ``direct``
                        （浏览器直连 hls.js 是站点自己的播放方式），
                        **但上生产前必须在真实网络里点开一集确认分片**；
                        若分片仍 403，把 ``mode`` 改成 ``"proxy"`` 走后端中继。
======================  ==================================================

（这条就是项目文档里那条经验的复现：只测清单最容易骗过自己，
清单 200 不代表分片能播。）
"""

from __future__ import annotations

import json
import os
import re
import sys


def _bootstrap_kit_path() -> None:
    """把 ``crawler_kit`` 的父目录挂进 sys.path。

    后端热部署时会注入 ``CRAWLER_KIT_PATH`` / ``PYTHONPATH``；本地直接
    ``python huangguoai.py``（脚本放在桌面上）时，这里沿目录向上一层层找
    ``crawler/crawler_kit/__init__.py`` 兜底 —— 不做魔法，只认这个特征文件。
    """
    roots = [os.environ.get("CRAWLER_KIT_PATH") or ""]
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        roots.append(here)
        roots.append(os.path.join(here, "crawler"))
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    for root in roots:
        if root and os.path.isfile(os.path.join(root, "crawler_kit", "__init__.py")):
            if root not in sys.path:
                sys.path.insert(0, root)
            return


_bootstrap_kit_path()

try:
    from crawler_kit import Client, CrawlerError, clean, cli, log, parse  # noqa: E402
except ImportError as exc:  # pragma: no cover - 只在工具箱不可见时走到
    # 硬规矩：失败也要给一行 JSON 信封 + 退出码 0，别让调用方只看到一段栈
    print(
        json.dumps(
            {
                "ok": False,
                "data": None,
                "error": {
                    "code": "UNKNOWN",
                    "message": (
                        f"crawler_kit 不可用（{exc}）：请把仓库的 crawler/ 目录放进 PYTHONPATH，"
                        "或设 CRAWLER_KIT_PATH 指向它"
                    ),
                },
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0)

# --------------------------------------------------------------------- 常量

KEY = "huangguoai"
NAME = "黄果短剧官网"
BASE_URL = "https://huangguoai.com/"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
#: 该源只有一条线路（epPlaySrcs 的键是集号，不是线路号）
LINE_NAME = "默认线路"

#: 影片路径：``/video/<id>/``
_DETAIL_HREF_RE = re.compile(r"/video/(\d+)/")
#: 可当分类用的导航：4 个 AI 频道 + 排行榜
#: （``/topics/`` 专题、``/chigua/`` 社区、``/go-home/`` APP 下载都不是影片列表）
_CHANNEL_HREF_RE = re.compile(r"^/(ai-[\w-]+|ranks/hot)/$")
#: 题材标签页：``/tag/<slug>/``（真实可翻页的列表页，拿它当二级分类）
_TAG_HREF_RE = re.compile(r"^/tag/([\w-]+)/$")
#: 分类 tid 的合法形态（``ai-duanju``、``tag/dushi``、``ranks/hot``）
_TID_RE = re.compile(r"[\w-]+(?:/[\w-]+)*")
#: play_id 复合定位符：``<vod_id>|<line>|<ep>``
_PLAY_ID_RE = re.compile(r"^(\d{1,12})\|(\d{1,4})\|(\d{1,6})$")
#: play_id 的另一种形态：站内集页相对路径
_EP_PATH_RE = re.compile(r"^/video/(\d+)/(?:ep-(\d+)/)?$")
#: 详情/集页内嵌的 JSON 信令块
_INITIAL_DATA_RE = re.compile(r'<script id="videoInitialData"[^>]*>(.*?)</script>', re.S)
#: 卡片/标题里的水印尾巴
_FOLLOW_SUFFIX_RE = re.compile(r"\s*\+\s*关注\s*$")
#: 排行榜行里以「9.7分」形式出现的评分
_SCORE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*分")


# ------------------------------------------------------------------ 解析工具
def _direct_text(node) -> str:
    """只取节点的**直接**文本子节点。

    卡片标题与题材标签内部都塞了 ``span.sr-only`` 水印
    （「全集在线观看」「都市题材短剧 · 《…》」），取后代 ``text`` 会把水印
    当成片名/标签名带出去，所以这里只拼直接文本。
    """
    if node is None:
        return ""
    return clean.collapse("".join(child.data or "" for child in node.children if child.is_text))


def _in_noise(node) -> bool:
    """卡片是不是躺在不可信容器里。

    三类噪音：首页搜索建议面板（``hg-search-suggest``，同款卡片但整块隐藏）、
    带 ``hidden`` 属性或行内隐藏的面板、``<template>`` 翻版卡片模板。
    """
    parent = node.parent
    while parent is not None:
        if parent.tag == "template" or "hidden" in parent.attrs or parent.is_hidden:
            return True
        if "hg-search-suggest" in (parent.attrs.get("class") or ""):
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
    except ValueError as exc:
        log.warn(f"videoInitialData 不是合法 JSON: {exc}")
        return {}
    return payload if isinstance(payload, dict) else {}


def _year(value) -> int:
    """``"2026-09-30 13:34:47"`` -> ``2026``；抠不到就返回 0（不猜）。"""
    text = str(value or "").strip()
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else 0


def _fact_value(node) -> str:
    """取 ``.hg-web-play__fact`` 的值，并去掉「+关注」按钮文本。"""
    holder = node.select_first("span")
    value = holder.text if holder is not None else ""
    return _FOLLOW_SUFFIX_RE.sub("", clean.collapse(value)).strip()


def _facts(root) -> dict:
    """详情页「影片信息」栅格 -> ``{标签: 值}``。

    实测标签有：上线日期 / 出品 / 更新状态 / 播放次数 / 单集片长 / 题材类型。
    站点**没有**演员、导演、地区字段 —— 所以这里做成通用映射：
    站点哪天加上了「主演」，契约里的 ``vod_actor`` 就会自动有值。
    """
    out = {}
    for node in root.select("div.hg-web-play__fact"):
        label_node = node.select_first("b")
        label = clean.collapse(label_node.text) if label_node is not None else ""
        value = _fact_value(node)
        if label and value:
            out.setdefault(label, value)
    return out


# ------------------------------------------------------------------ 列表映射
def _card(node):
    """``div.hg-drama-card`` -> VodItem。缺片名的一律丢弃，不伪造。"""
    if _in_noise(node):
        return None

    link = node.select_first("a.hg-drama-card__cover-link")
    if link is None:
        link = node.select_first('a[href^="/video/"]')
    if link is None:
        return None
    matched = _DETAIL_HREF_RE.search(link.attr("href") or "")
    if not matched:
        return None

    name = ""
    title = node.select_first(".hg-drama-card__title")
    if title is not None:
        name = _direct_text(title.select_first("a")) or _direct_text(title)
    if not name:
        image = link.select_first("img")
        name = clean.strip_promo(image.attr("alt") or "") if image is not None else ""
    if not name:
        return None

    video = {
        "vod_id": matched.group(1),
        "vod_name": name,
        "vod_pic": clean.absolute(parse.first_image(link), BASE_URL),
        "vod_remarks": "",
    }

    episode = node.select_first(".hg-drama-card__episode")
    if episode is not None:
        # data-ep-base 是干净的「更新至9集」；元素 text 里混着「19小时前」这类相对时间
        remarks = episode.attr("data-ep-base") or _direct_text(episode) or episode.text
        video["vod_remarks"] = clean.strip_promo(remarks)

    tags = _tags_of(node)
    if tags:
        video["vod_type"] = ",".join(tags)

    score_node = node.select_first(".hg-drama-card__score")
    score = clean.to_float(score_node.text) if score_node is not None else None
    if score:
        video["vod_score"] = score
    # 注意：列表卡片上没有年份字段（只有上架/更新时间戳），不拿时间戳冒充 `vod_year`
    return video


def _tags_of(node):
    """卡片上的题材标签名（去掉 sr-only 水印）。"""
    out = []
    for anchor in node.select(".hg-drama-card__tags a.hg-tag"):
        name = _direct_text(anchor)
        if name and name not in out:
            out.append(name)
    return out


def _cards(root):
    out = []
    for node in root.select("div.hg-drama-card"):
        card = _card(node)
        if card is not None:
            out.append(card)
    return clean.dedupe(out, key=lambda item: item["vod_id"])


def _rank_item(node):
    """``div.hg-rank-item`` -> VodItem。

    榜单用的是**行式卡片**（``/ranks/hot/`` 上 20 行），跟列表页的
    ``div.hg-drama-card`` 不是同一套标记，页面上另有 4 张普通卡片（推荐位）。
    榜单行里没有「更新至N集」，硬凑就是编造 —— 所以 ``vod_remarks`` 用行内
    真实展示的热度指数；评分从「· 9.7分」里取。
    """
    if _in_noise(node):
        return None

    link = node.select_first("a.hg-rank-item__cover")
    if link is None:
        link = node.select_first('a[href^="/video/"]')
    if link is None:
        return None
    matched = _DETAIL_HREF_RE.search(link.attr("href") or "")
    if not matched:
        return None

    name = _direct_text(node.select_first(".hg-rank-item__title a"))
    if not name:
        name = _direct_text(node.select_first(".hg-rank-item__title"))
    if not name:
        image = link.select_first("img")
        name = clean.strip_promo(image.attr("alt") or "") if image is not None else ""
    if not name:
        return None

    video = {
        "vod_id": matched.group(1),
        "vod_name": name,
        "vod_pic": clean.absolute(parse.first_image(link), BASE_URL),
        "vod_remarks": "",
    }
    heat = node.select_first(".hg-rank-item__heat-value")
    if heat is not None:
        heat_text = clean.collapse(heat.text)
        if heat_text:
            video["vod_remarks"] = f"热度 {heat_text}"

    tags_node = node.select_first(".hg-rank-item__tags")
    if tags_node is not None:
        tags = []
        for anchor in tags_node.select("a"):
            if not _TAG_HREF_RE.match(anchor.attr("href") or ""):
                continue
            name_text = _direct_text(anchor)
            if name_text and name_text not in tags:
                tags.append(name_text)
        if tags:
            video["vod_type"] = ",".join(tags)
        matched_score = _SCORE_RE.search(tags_node.text)
        score = clean.to_float(matched_score.group(1)) if matched_score else None
        if score:
            video["vod_score"] = score
    return video


def _rank_items(root):
    out = []
    for node in root.select("div.hg-rank-item"):
        item = _rank_item(node)
        if item is not None:
            out.append(item)
    return clean.dedupe(out, key=lambda item: item["vod_id"])


def _list_items(root):
    """列表页的影片：普通卡片 + 排行榜行（两种标记都可能同时出现，去重后返回）。"""
    return clean.dedupe(_cards(root) + _rank_items(root), key=lambda item: item["vod_id"])


def _category_items(root):
    """首页「分类推荐」栏的 ``a.hg-category-item`` -> VodItem（补充推荐）。"""
    out = []
    for anchor in root.select("a.hg-category-item"):
        if _in_noise(anchor):
            continue
        matched = _DETAIL_HREF_RE.search(anchor.attr("href") or "")
        if not matched:
            continue
        name = _direct_text(anchor.select_first(".hg-category-item__title"))
        if not name:
            continue
        out.append(
            {
                "vod_id": matched.group(1),
                "vod_name": name,
                "vod_pic": clean.absolute(parse.first_image(anchor), BASE_URL),
                "vod_remarks": "",
            }
        )
    return out


def _categories(root):
    """顶栏 + 侧栏导航 -> 一级分类（4 个 AI 频道 + 排行榜）。"""
    out = []
    seen = set()
    for css in (".hg-topbar-nav__item", ".hg-nav-item"):
        for anchor in root.select(css):
            matched = _CHANNEL_HREF_RE.match(anchor.attr("href") or "")
            if not matched:
                continue
            tid = matched.group(1)
            if tid in seen:
                continue
            name = clean.collapse(anchor.text)
            if not name:
                continue
            seen.add(tid)
            out.append({"tid": tid, "name": name})
    return out


def _tag_links(root, limit=12):
    """卡片上的题材标签 -> 二级分类 ``{tid: "tag/<slug>", name: "都市"}``。

    按出现次数排序（该频道最热门的题材排前面）。``/tag/<slug>/`` 是真实
    可翻页的列表页 —— 前台点一下就能直接落到 ``category``。
    """
    counter = {}
    order = {}
    for node in root.select("div.hg-drama-card"):
        if _in_noise(node):
            continue
        for anchor in node.select(".hg-drama-card__tags a.hg-tag"):
            href = anchor.attr("href") or ""
            matched = _TAG_HREF_RE.match(href)
            name = _direct_text(anchor)
            if not matched or not name:
                continue
            slug = matched.group(1)
            counter[slug] = counter.get(slug, 0) + 1
            order.setdefault(slug, (name, len(order)))
    ranked = sorted(order, key=lambda slug: (-counter[slug], order[slug][1]))
    return [{"tid": f"tag/{slug}", "name": order[slug][0]} for slug in ranked[:limit]]


def _total_pages(root):
    """分页条上的总页数（``.hg-pager__jump[data-pages]`` 实测每页都带）。"""
    jump = root.select_first(".hg-pager__jump")
    total = clean.to_int(jump.attr("data-pages")) if jump is not None else None
    if total:
        return total
    best = 0
    for anchor in root.select("a.hg-pager__page"):
        best = max(best, clean.to_int(anchor.text, 0) or 0)
    return best


def _has_more(root, page: int) -> bool:
    """还有下一页吗。优先看总页数，其次看页码链接，最后看「下一页」箭头。"""
    total = _total_pages(root)
    if total:
        return page < total
    return root.select_first('a.hg-pager__arrow[rel="next"]') is not None


def _page_path(tid: str, page: int) -> str:
    """页码段有**两种**格式（实测）：频道 ``/<tid>/<页>/``、标签 ``/<tid>/page/<页>/``。"""
    if page <= 1:
        return f"/{tid}/"
    if tid.startswith("tag/"):
        return f"/{tid}/page/{page}/"
    return f"/{tid}/{page}/"


def _episode_name(index: int) -> str:
    return f"第{index:02d}集"


def _episodes(root, vid: str, play_line: int = 1):
    """选集锚点 -> episodes（``ep_index`` 1 起算；``play_id`` 是复合定位符）。

    实测长剧也**一次渲染完**（27 集 / 26 集的剧都验证过锚点数与「更新至N集」一致，
    没有懒加载、没有「展开更多」接口），所以这里不需要翻页。
    """
    out = []
    for anchor in root.select("a.hg-web-play__ep"):
        index = clean.to_int(anchor.attr("data-ep-id"))
        if index is None or index < 1:
            continue
        out.append(
            {
                "ep_index": index,
                "ep_name": _episode_name(index),
                "play_id": f"{vid}|{play_line}|{index}",
                "line": play_line,
            }
        )
    out.sort(key=lambda item: item["ep_index"])
    return clean.dedupe(out, key=lambda item: item["ep_index"])


def _parse_play_id(value):
    """``play_id`` -> ``(vod_id, line, ep)``；解析不出来返回 ``None``。

    这个值是**上层回传**的，所以只在两种白名单形态里认（都是形态校验，
    不接受 URL、不接受路径穿越 —— 后一种走 ``clean.safe_relative_path`` 收敛）：
    ``7420|1|2`` 与 ``/video/7420/ep-2/``。不认的值直接丢，退回慢路径。
    """
    text = str(value or "").strip()
    if not text:
        return None
    matched = _PLAY_ID_RE.match(text)
    if matched:
        return (
            matched.group(1),
            clean.to_int(matched.group(2), 1) or 1,
            clean.to_int(matched.group(3), 1) or 1,
        )
    path = clean.safe_relative_path(text)
    matched = _EP_PATH_RE.match(path) if path else None
    if matched:
        return (matched.group(1), 1, clean.to_int(matched.group(2), 1) or 1)
    return None


# ------------------------------------------------------------------ 解密扩展
def decode_image(content: bytes) -> tuple[bytes, str] | None:
    """针对黄果短剧前端 AES-128-CBC 加密的封面图片进行自动解密。

    若输入不是加密字节流或解密失败返回 None；
    解密成功返回 (decrypted_bytes, content_type)。
    """
    if not content or len(content) < 16:
        return None
    # 常见标准图片头部直接跳过
    if (
        content.startswith(b"\xff\xd8\xff")  # JPEG
        or content.startswith(b"\x89PNG")    # PNG
        or content.startswith(b"RIFF")       # WEBP
        or content.startswith(b"GIF8")       # GIF
    ):
        return None

    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        # 黄果短剧的固定媒体密钥 (来自 plugins/crypto-worker.js)
        cipher = Cipher(
            algorithms.AES(b"f5d965df75336270"),
            modes.CBC(b"97b60394abc2fbe1"),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(content) + decryptor.finalize()
        if decrypted.startswith(b"\xff\xd8\xff"):
            return decrypted, "image/jpeg"
        if decrypted.startswith(b"\x89PNG"):
            return decrypted, "image/png"
        if decrypted.startswith(b"RIFF"):
            return decrypted, "image/webp"
        return None
    except Exception:
        return None


# ----------------------------------------------------------------------- 站点
class 黄果短剧官网Crawler:
    """黄果短剧官网采集器（单文件适配器）。"""

    @staticmethod
    def decode_image(content: bytes) -> tuple[bytes, str] | None:
        """图片解密钩子。"""
        return decode_image(content)


    key = KEY
    name = NAME
    #: 语义化版本号；后台覆盖部署时支持自动 patch 递增
    version = "1.0.0"
    base_url = BASE_URL
    #: direct = 播放器直连源站 CDN；proxy = 需后端中继（见模块 docstring 的分片 403 说明）
    mode = "direct"
    capabilities = ("meta", "home", "category", "detail", "play")

    def __init__(self, client=None):
        #: 内置高性能 Client（自动重试、连接池、限速）
        self.http = client or Client(
            base_url=self.base_url,
            timeout=15.0,
            retries=1,
            headers={
                "User-Agent": DEFAULT_UA,
                "Referer": self.base_url,
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            min_interval=0.3,
        )

    # ---------------------------------------------------------------- 基础

    def _page(self, path: str) -> str:
        response = self.http.get(path)
        if response.status in (404, 410):
            raise CrawlerError("NOT_FOUND", f"页面不存在: {path}")
        if not response.ok:
            raise CrawlerError("HTTP_ERROR", f"{path} 返回 HTTP {response.status}")
        html = response.text
        log.debug(f"GET {path} -> HTTP {response.status}，{len(html)} 字符")
        return html

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

    def _channel_tags(self, tid: str, limit: int = 12):
        """二级分类 = 该频道自己页面上的题材标签；取不到就留空，不让 home 整体失败。"""
        try:
            root = parse.parse_html(self._page(f"/{tid}/"))
        except CrawlerError as exc:
            log.warn(f"{tid} 的题材标签取不到（{exc.message}），二级分类留空")
            return []
        return _tag_links(root, limit=limit)

    # ---------------------------------------------------------------- 动作

    def meta(self):
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "mode": self.mode,
            "capabilities": list(self.capabilities),
            "play_format": ["m3u8", "mp4"],
            "note": (
                "SSR 站点；频道 /<tid>/、分页 /<tid>/<页>/（标签页是 /tag/<slug>/page/<页>/）；"
                "详情 /video/<id>/、选集 /video/<id>/ep-<n>/；m3u8 明文写在 videoInitialData 里，"
                "epPlaySrcs 只给当前集±1，地址现签、不可缓存"
            ),
        }

    def home(self):
        """首页：分类树（含二级题材）+ 推荐片单。"""
        root = parse.parse_html(self._page("/"))
        common_tags = _tag_links(root, limit=12)
        categories = []
        for item in _categories(root):
            subcategories = [{"tid": item["tid"], "name": f"全部{item['name']}"}]
            if item["tid"] != "ranks/hot":
                subcategories.extend(common_tags)
            categories.append(
                {"tid": item["tid"], "name": item["name"], "subcategories": subcategories}
            )

        recommend = _list_items(root) + _category_items(root)
        return {
            "categories": categories,
            "recommend": clean.dedupe(recommend, key=lambda item: item["vod_id"]),
        }

    def category(self, tid, page=1):
        """分类 / 题材列表（分页）。"""
        tid = self._check_tid(tid)
        page = max(1, clean.to_int(page, 1) or 1)
        path = _page_path(tid, page)
        root = parse.parse_html(self._page(path))
        videos = _list_items(root)
        has_more = _has_more(root, page)
        log.debug(f"category {tid} page={page}: {len(videos)} 条，has_more={has_more}")
        return {"videos": videos, "page": page, "has_more": has_more}

    def detail(self, id):
        """详情 + 线路 + 逐集定位符。"""
        vid = self._check_id(id)
        html = self._page(f"/video/{vid}/")
        data = _initial_data(html)
        root = parse.parse_html(html)
        if not data and root.select_first("a.hg-web-play__ep") is None:
            raise CrawlerError("PARSE_ERROR", f"详情页结构不认识（没有视频信令）: {vid}")

        name = clean.strip_promo(str(data.get("title") or ""))
        if not name:
            heading = root.select_first("h1")
            name = clean.strip_promo(_direct_text(heading) or (heading.text if heading else ""))
        if not name:
            raise CrawlerError("PARSE_ERROR", f"详情页没有解析到片名: {vid}")

        episodes = _episodes(root, vid)
        if not episodes:
            # 单集剧可能不渲染选集列表：至少保住信令里声明的当前集
            current = max(1, clean.to_int(data.get("ep"), 1) or 1)
            episodes = [
                {
                    "ep_index": current,
                    "ep_name": _episode_name(current),
                    "play_id": f"{vid}|1|{current}",
                    "line": 1,
                }
            ]

        facts = _facts(root)
        poster = root.select_first(".hg-web-play__poster img")
        video = {
            "vod_id": str(clean.to_int(data.get("id"), vid) or vid),
            "vod_name": name,
            "vod_pic": clean.absolute(
                data.get("coverSrc")
                or data.get("posterSrc")
                or (poster.attr("data-src") or poster.attr("src") if poster is not None else ""),
                BASE_URL,
            ),
            "vod_remarks": clean.strip_promo(
                facts.get("更新状态")
                or (f"更新至{len(episodes)}集" if len(episodes) > 1 else "")
            ),
        }

        tags = [
            clean.strip_promo(str(tag))
            for tag in (data.get("tags") or [])
            if clean.strip_promo(str(tag))
        ]
        if tags:
            video["vod_type"] = ",".join(tags)

        year = _year(data.get("time")) or _year(facts.get("上线日期") or facts.get("上映日期"))
        if year:
            video["vod_year"] = year

        # 站点给什么填什么：没有的键不编造（见模块 docstring）
        for label, field in (("主演", "vod_actor"), ("演员", "vod_actor"), ("导演", "vod_director")):
            if facts.get(label) and field not in video:
                video[field] = clean.strip_promo(facts[label])
        for label in ("地区", "制片地区", "国家"):
            if facts.get(label):
                video["vod_area"] = clean.strip_promo(facts[label])
                break

        desc = clean.strip_promo(str(data.get("description") or ""))
        if not desc:
            synopsis = root.select_first(".hg-web-play__synopsis-text p")
            desc = clean.strip_promo(synopsis.text if synopsis is not None else "")

        line = {
            "id": "1",
            "name": LINE_NAME,
            "episodes": episodes,
            # 下面两个键是给本系统后端 DetailPayload.lines（LineInfo）用的，多余键会被忽略
            "line": 1,
            "count": len(episodes),
        }
        return {
            "video": video,
            "desc": desc,
            "lines": [line],
            # 顶层 episodes 是后端契约的形状（平铺 + line），与 lines[].episodes 同源
            "episodes": episodes,
        }

    def play(self, id=None, ep=1, play_id=None, line=1):
        """取真实播放地址（m3u8 现签，不可缓存）。"""
        line_no = max(1, clean.to_int(line, 1) or 1)
        if line_no > 1:
            log.warn(f"该源只有一条线路，忽略 --line {line_no}")
        index = max(1, clean.to_int(ep, 1) or 1)

        vid = None
        located = _parse_play_id(play_id)
        if located:
            located_id, _, located_ep = located
            if id is not None and self._check_id(id) != located_id:
                log.warn(f"play_id 与 --id 不一致，按 --id 处理: {located_id} != {id}")
            else:
                vid = self._check_id(located_id)
                # play_id 自带的集号优先于 --ep（它是详情里下发的精确定位符）
                if located_ep != index:
                    log.debug(f"play_id 指定第 {located_ep} 集，覆盖 --ep {index}")
                index = located_ep
        elif play_id:
            log.warn(f"忽略不可信的 play_id（不是 站内集页路径 / id|line|ep）: {str(play_id)[:80]!r}")

        if vid is None:
            if id is None:
                raise CrawlerError(
                    "NOT_FOUND", "play 需要 --id，或传一个合法的 --play-id（详情里每集都带）"
                )
            vid = self._check_id(id)

        path = f"/video/{vid}/" if index <= 1 else f"/video/{vid}/ep-{index}/"
        data = _initial_data(self._page(path))
        if not data:
            raise CrawlerError("PARSE_ERROR", f"集页缺少视频信令: {path}")

        page_ep = max(1, clean.to_int(data.get("ep"), index) or index)
        if page_ep != index:
            log.warn(f"站点返回第 {page_ep} 集（请求第 {index} 集）: {path}")

        sources = data.get("epPlaySrcs") or {}
        url = str(sources.get(str(page_ep)) or data.get("videoSrc") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise CrawlerError("PARSE_ERROR", f"第 {page_ep} 集没有可用的播放地址")

        suffix = url.split("?", 1)[0].split("#", 1)[0].lower()
        fmt = "mp4" if suffix.endswith(".mp4") else "m3u8"
        return {"url": url, "format": fmt, "headers": {"Referer": self.base_url}}


#: 给不习惯中文类名的调用方留一个 ASCII 别名
HuangguoaiCrawler = 黄果短剧官网Crawler


if __name__ == "__main__":
    cli.main(黄果短剧官网Crawler())
