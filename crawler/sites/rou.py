#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""rou.video（肉視頻，本系统里的源名「首頁」）单文件采集器 / 适配器。

站点形态（2026-10-02 实测，全部为真抓样本，不是推测；抓样见文末「实测记录」）
--------------------------------------------------------------------------
* **TanStack Start SSR**（Vite SPA 外壳 + 服务端直出 HTML），列表数据全在 HTML 里，
  纯 HTTP 就能抓；Cloudflare 只在前面走了缓存，实测裸 GET 直接 200，无挑战页。
* 路由：
  - ``/home`` 首页（一堆 h2 栏 + 卡片），``/cat`` 標籤總覽（134 个標籤卡片）
  - ``/v?page=N`` 全部影片（每页 26 条）、``/series?page=N`` 劇集（每页 26 条）
  - ``/t/<標籤>?page=N`` 標籤列表（每页 26 条，標籤名是 URL 编码的原文）
  - ``/v/<cuid>`` 影片详情、``/s/<cuid>`` 劇集详情
* id 是 **25 位 cuid**（如 ``cmu8ng3q60004s6x3byujkmig``），不是数字。
* 卡片统一是 ``a.group.block``（首页栏、列表页、劇集卡片同一套标记）：
  封面 ``img``（懒加载但 SSR 已带 src）、片名 ``h3``、封面角标 ``span``（``720 P``）、
  时长 ``div``（``37:06``）、劇集卡片另有 ``全 10 集`` 角标。
* 详情页五件套走 ``<meta property="og:*">``（title / image / description / url），
  正文顺序：``h1`` 片名 → 数据行 → ``a[href^="/t/"]`` 標籤（第一个是主分类，
  其余带 ``#`` 前缀）→ 简介 ``details``；劇集剧集列表在 ``aside`` 的
  「劇集列表 共 N 集」卡片里，**每行都带序号角标**（``span.tabular-nums``），
  该卡片同时带 ``a[href^="/s/<seriesId>"]`` —— 这是把"剧集行"和"相关推荐"
  区分开的唯一可靠特征（相关推荐卡片没有序号角标）。

播放地址（这是本源的**最大坑**，必须按实测来，别按想象写）
----------------------------------------------------------
1. 详情页内嵌状态里有 ``ev:$R[n]={d:"<base64>",k:<int>}`` —— 站点前端的
   ``decryptRouVideo``：``atob(d)`` 后**逐字符减去 k** 再 ``JSON.parse``，解出::

       {"videoUrl": "/api/hls/<video_id>", "thumbVTTUrl": "/api/hls/<id>?kind=thumbs"}

   等价 Python：``bytes((b - k) % 256 for b in base64.b64decode(d)).decode("utf-8")``。
2. ``GET /api/hls/<video_id>`` 返回 **302**，落到 CDN 的
   ``https://<随机主机>.xyz/hls/<id>/<id>-720/index.png?v=6&exp=<ts>&auth=<sig>``。
   路径叫 ``.png``、``Content-Type: image/png``，**但它根本不是图片**：
   它是**伪装成 PNG 的 HLS 清单** —— PNG 文件头 + 若干「4 字节长度 + 4 字节 tag +
   载荷 + 4 字节 CRC」的 chunk，其中 tag 为 ``roUd``（``0x726F5564``，就是站名的
   大小写把戏）的 chunk 里是 ``[1 字节 flags] + payload``：
   ``flags & 1`` → payload 是 **zlib(deflate)** 压缩（清单就是这样），
   否则是裸数据（``.ts`` 分片就是这样，实测分片 2.18MB、首字节是 TS 同步字 ``0x47``）。
3. 清单里的分片形如 ``<id>-720/C-000.png ... C-031.png``（同样是伪装名），
   主机在 ``v1..v5.<随机>.xyz`` 之间轮换，``exp/auth`` 签名与清单同源。
4. 站点自己的播放器是 shaka-player + ``registerResponseFilter``，**在浏览器里**
   对 MANIFEST 与 SEGMENT 两类响应做上面这套解封装。

**因此本适配器 ``mode = "proxy"``**（不是模板里的 direct）：任何直连播放器
（hls.js / 原生 video）拿到的都是「PNG」，必须由我们的中继按 :func:`decode_media`
解封装后再往外吐。``play()`` 返回的 ``url`` 是站点入口 ``/api/hls/<id>``
（每次现签、**不可缓存**），返回里另附 ``wrapper`` / ``decoded_type`` /
``segment_count`` / ``cacheable: false`` 供后端与排查使用。

顺带记一笔：主清单（把 302 目标里的 ``<id>-720/`` 段去掉即得）实测**只有一条**
``#EXT-X-STREAM-INF:BANDWIDTH=2560000`` 变体，直取变体清单即可，本适配器不做画质选择。

封面（``v.rn252.xyz/m/...``）实测是**普通 JPEG**（388KB、无 Referer 限制），
所以**不需要** ``decode_image`` 钩子；本源的混淆只发生在媒体面，不在图片面。

契约说明
--------
* ``vod_id``：影片是 cuid（``cmu...``），劇集是 ``s/<cuid>`` 前缀形态（因为劇集卡片
  本身指向 ``/s/<id>``，前端点进来时必须能落回 ``detail``）；
* ``play_id``：**就是该集自己的 cuid**（这一源的播放地址只由 video_id 决定，
  不需要复合定位符）；``play()`` 同时兼容 ``<cuid>`` 与 ``<cuid>|<line>|<ep>`` 两种写法；
* 线路只有一条（站点就一条 HLS）：``lines`` 固定 1 条，``line > 1`` 只记日志不报错；
* ``detail`` 同时给 ``lines[].episodes``（本文件主契约）与顶层 ``episodes``
  （本系统后端 ``DetailPayload`` 的平铺形状），两者同源；
* 站点没有演员/导演/地区字段 —— **不编造**：抓得到就填，抓不到就不给这个键。

用法::

    # 后端热部署会自动注入 CRAWLER_KIT_PATH / PYTHONPATH；本地手跑：
    PYTHONPATH=<repo>/crawler python crawler/sites/rou.py meta
    PYTHONPATH=<repo>/crawler python crawler/sites/rou.py home
    PYTHONPATH=<repo>/crawler python crawler/sites/rou.py category --tid v --page 2
    PYTHONPATH=<repo>/crawler python crawler/sites/rou.py category --tid 't/AI短劇'
    PYTHONPATH=<repo>/crawler python crawler/sites/rou.py detail --id cmu8ng3q60004s6x3byujkmig
    PYTHONPATH=<repo>/crawler python crawler/sites/rou.py play --id cmu8ng3q60004s6x3byujkmig
    PYTHONPATH=<repo>/crawler python crawler/sites/rou.py play --play-id cmudrw2af0000mu8gl94mmrx1

实测记录（2026-10-02，真抓；改选择器前请先复现，别凭感觉）
----------------------------------------------------------
======================  ============================================================
``/home``               点击计数 HTTP 200、382KB、SSR 直出，109 个 ``a[href^="/v/"]``
``/v?page=2``           200、每页 26 张卡片、分页条 ``aria-label="第 2146 頁"``（末页可读）
``/cat``                200、134 个 ``/t/`` 標籤卡片；页内 h2 分组不可单独成路由（故不作一级分类）
详情页 ``/v/<cuid>``    200、77KB；``og:image`` = JPEG 封面；劇集页 ``aside`` 列出该劇集**全部**集
``/api/hls/<id>``       302 → CDN 伪装 PNG 清单（实测解出 6766 字节、32 个分片、``#EXT-X-VERSION:3``）
主清单                  ``/hls/<id>/index.*``（实测把路径里的 ``<id>-720`` 段去掉即得主清单，
                        ``#EXT-X-STREAM-INF:BANDWIDTH=2560000`` → 变体清单）
分片                    HTTP 200、2.18MB、解封装后是裸 MPEG-TS（``0x47`` 同步字）
封面                    HTTP 200、388KB 真 JPEG，带不带 Referer 都一样
======================  ============================================================
"""

from __future__ import annotations

import base64
import json
import os
import re
import struct
import sys
import zlib


def _bootstrap_kit_path() -> None:
    """把 ``crawler_kit`` 的父目录挂进 sys.path。

    后端热部署会注入 ``CRAWLER_KIT_PATH`` / ``PYTHONPATH``；本地直接
    ``python rou.py`` 时沿目录向上一层层找 ``crawler/crawler_kit/__init__.py`` 兜底。
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

KEY = "rou"
NAME = "肉視頻"
VERSION = "1.0.1"
#: 站点 origin（Client 的 base_url 必须是它，不能带 /home —— 否则 /v/x 会拼成 /home/v/x）
SITE = "https://rou.video"
#: 契约要求的 base_url：本源在系统里登记的入口就是首页
BASE_URL = SITE + "/home"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
#: 该源只有一条线路（站点只有一份 HLS）
LINE_NAME = "默認線路"
#: 主动限速：一条命令里会连打好几个请求，保守取 0.3s（契约里也是这个值）
MIN_REQUEST_INTERVAL = 0.3

#: 伪 PNG 容器：文件头是 PNG 签名，payload 挂在 tag 为 "roUd" 的 chunk 里
PNG_MAGIC = bytes((137, 80, 78, 71, 13, 10, 26, 10))
ROUD_TAG = 0x726F5564  # 'roUd'（站名的大小写把戏）
#: chunk 里的 flags：置位表示 payload 是 zlib/deflate 压缩的
FLAG_DEFLATE = 1

#: 影片 id（cuid）：25 位小写字母数字，放宽到 16–40 位容忍站点换 id 方案
_CUID_RE = re.compile(r"^[a-z0-9]{16,40}$")
#: 卡片/详情链接：``/v/<cuid>`` 或 ``/s/<cuid>``
_ITEM_HREF_RE = re.compile(r"^/(v|s)/([a-z0-9]{16,40})$")
#: 详情页内嵌的加密播放信令：``ev:$R[99]={d:"...",k:29}``
_EV_RE = re.compile(r'ev:\$R\[\d+\]=\{d:"([^"]+)",k:(\d+)\}')
#: 详情页内嵌状态里的 video 字面量（用来补 year / duration，取不到就不给这些键）
_VIDEO_STATE_RE = re.compile(r"video:\$R\[\d+\]=\{(.*?)\}", re.S)
#: 角标特征
_QUALITY_RE = re.compile(r"^\d{3,4}\s*[pP]$")
_DURATION_RE = re.compile(r"^\d{1,2}(?::\d{2}){1,2}$")
_EP_LABEL_RE = re.compile(r"全\s*\d+\s*集")
#: 「劇集列表 共 N 集」
_TOTAL_EP_RE = re.compile(r"共\s*(\d+)\s*集")
#: 劇集页宫格块上的「第 N 集」
_EP_INDEX_RE = re.compile(r"第\s*(\d+)\s*集")
#: 分页条：``aria-label="第 2146 頁"``
_PAGE_LABEL_RE = re.compile(r"第\s*(\d+)\s*頁")
#: 分类 tid 的合法形态：``v`` / ``series`` / ``t/<標籤>``
_TID_RE = re.compile(r"^(?:v|series|t/[^/\\]{1,64})$")


# ------------------------------------------------------- 伪 PNG 容器解封装

def decode_media(content: bytes) -> bytes | None:
    """解开封在伪 PNG 容器里的 HLS 响应；不是这种容器就返回 ``None``。

    容器格式（实测，与站点前端 ``$k()`` 完全一致）::

        <PNG 签名 8 字节>
        [4B 长度][4B tag][载荷][4B CRC]  <- 若干 chunk，前面几个是装饰用的真 PNG chunk
        ...
        [4B 长度][4B 'roUd'][1B flags][payload][4B CRC]

    其中 ``payload`` 长度为「长度 - 1」，``flags & 1`` 时 payload 是 deflate(zlib)。

    返回值用途：
      * ``b"#EXTM3U"`` 开头 → 解开的是 **HLS 清单**（文本）；
      * ``0x47`` 开头 → 解开的是 **MPEG-TS 分片**（二进制）。

    阶段 9 的流代理/前端播放器必须调用它（或本文件的同名类方法），
    否则拿到手的是一条「``image/png``」——播放器会直接判为非法清单。
    """
    if not content or len(content) < len(PNG_MAGIC) + 8:
        return None
    if not content.startswith(PNG_MAGIC):
        return None

    total = len(content)
    offset = len(PNG_MAGIC)
    while offset + 8 <= total:
        length, tag = struct.unpack(">II", content[offset:offset + 8])
        body_start = offset + 8
        if length < 1 or body_start + length > total:
            break
        if tag == ROUD_TAG:
            flags = content[body_start]
            payload = content[body_start + 1:body_start + length]
            if flags & FLAG_DEFLATE:
                try:
                    return zlib.decompress(payload)
                except zlib.error as exc:
                    log.warn(f"roUd chunk 解压失败: {exc}")
                    return None
            return payload
        offset = body_start + length + 4  # 4 字节是 chunk 尾的 CRC
    return None


def _decrypt_ev(d: str, k: int) -> dict:
    """复刻站点前端 ``decryptRouVideo(d, k)``：atob 后逐字符减 k，再 JSON.parse。"""
    try:
        raw = base64.b64decode(d)
    except (ValueError, TypeError) as exc:
        raise CrawlerError("PARSE_ERROR", f"播放信令不是合法 base64: {exc}") from exc
    plain = bytes((b - k) % 256 for b in raw)
    try:
        payload = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CrawlerError("PARSE_ERROR", f"播放信令解密后不是 JSON: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def _play_signal(html: str) -> dict:
    """从详情页内嵌状态里取 ``ev`` 并解出 ``{videoUrl, thumbVTTUrl}``。"""
    matched = _EV_RE.search(html or "")
    if not matched:
        raise CrawlerError("PARSE_ERROR", "详情页里找不到播放信令 ev:{d,k}（结构可能已变）")
    key = clean.to_int(matched.group(2), 0) or 0
    return _decrypt_ev(matched.group(1), key)


# ------------------------------------------------------------------ 映射层

def _state_video(html: str) -> dict:
    """详情页内嵌状态里的 video 字面量 → 少量标量字段（取不到就空着，不猜）。"""
    matched = _VIDEO_STATE_RE.search(html or "")
    if not matched:
        return {}
    body = matched.group(1)
    out = {}

    duration = parse.re_first(r"duration:(\d+(?:\.\d+)?)", body, 1, default=None)
    if duration is not None:
        seconds = clean.to_int(float(duration))
        if seconds:
            out["duration"] = seconds

    created = parse.re_first(r'createdAt:"([^"]+)"', body, 1, default="")
    year = clean.to_int(str(created)[:4], 0)
    if year:
        out["year"] = year

    for field, key in (("viewCount", "view_count"), ("likeCount", "like_count")):
        value = parse.re_first(rf"{field}:(\d+)", body, 1, default=None)
        if value is not None:
            out[key] = clean.to_int(value, 0) or 0
    return out


def _card_remarks(node) -> str:
    """卡片角标 → ``vod_remarks``。

    实测三种角标（都在封面框里）：
      * ``720 P`` / ``1280 P`` 画质；``37:06`` 时长；劇集卡片是 ``全 10 集``。
    取不到就留空 —— 不拿别的东西冒充备注。
    """
    quality = ""
    duration = ""
    label = ""
    for span in node.select("span"):
        text = clean.collapse(span.text)
        if not text:
            continue
        if not label and _EP_LABEL_RE.match(text):
            label = text
        elif not quality and _QUALITY_RE.match(text):
            quality = text.replace(" ", "").upper()
    for box in node.select("div"):
        text = clean.collapse(box.text)
        if not duration and _DURATION_RE.match(text):
            duration = text
        if duration and quality:
            break

    if label:
        return label
    parts = [part for part in (quality, duration) if part]
    return " · ".join(parts)


def _card(node):
    """``a.group.block`` 卡片 → VodItem；缺 id 或缺片名的丢弃。"""
    matched = _ITEM_HREF_RE.match(node.attr("href") or "")
    if not matched:
        return None
    kind, cuid = matched.group(1), matched.group(2)

    name = ""
    heading = node.select_first("h3")
    if heading is not None:
        name = clean.strip_promo(heading.text)
    if not name:
        image = node.select_first("img")
        name = clean.strip_promo(image.attr("alt") or "") if image is not None else ""
    if not name:
        return None

    return {
        # 劇集卡片的 id 带 s/ 前缀，detail 才能区分「影片」与「劇集」
        "vod_id": cuid if kind == "v" else f"s/{cuid}",
        "vod_name": name,
        "vod_pic": clean.absolute(parse.first_image(node), SITE),
        "vod_remarks": _card_remarks(node),
    }


def _cards(root):
    """页面里的全部影片/劇集卡片（``a.group.block`` 同时覆盖两种，保持文档顺序）。"""
    out = []
    for node in root.select("a.group.block"):
        card = _card(node)
        if card is not None:
            out.append(card)
    return clean.dedupe(out, key=lambda item: item["vod_id"])


def _total_pages(root) -> int:
    """分页条上的最大页码（``aria-label="第 N 頁"``）。没有分页条就是 1 页。"""
    best = 1
    for anchor in root.select("a[href]"):
        label = anchor.attr("aria-label") or ""
        matched = _PAGE_LABEL_RE.search(label)
        if matched:
            best = max(best, clean.to_int(matched.group(1), 1) or 1)
    if best == 1:
        for anchor in root.select("a[href]"):
            for number in parse.re_all(r"[?&]page=(\d+)", anchor.attr("href") or "", 1):
                best = max(best, clean.to_int(number, 1) or 1)
    return best


def _tag_of_href(href: str) -> str:
    """``/t/%E6%97%A0%E7%A0%81`` → ``無碼``（站点把標籤名直接放在路径里）。"""
    if not (href or "").startswith("/t/"):
        return ""
    raw = href[3:].split("?", 1)[0].split("#", 1)[0]
    try:
        return clean.collapse(urllib.parse.unquote(raw))
    except Exception:  # noqa: BLE001 - 畸形百分号编码不值得抛
        return clean.collapse(raw)


def _detail_tags(root) -> list:
    """详情页標籤：第一个是主分类（无 ``#``），其余是 ``#`` 前缀的標籤。"""
    out = []
    for anchor in root.select('a[href^="/t/"]'):
        name = _tag_of_href(anchor.attr("href") or "")
        if name and name not in out:
            out.append(name)
    return out


def _build_rou_categories() -> list[dict]:
    """生成肉視頻完整的 8 大一级分类与细化二级分类树。"""
    guocan_tags = [
        "糖心Vlog", "蜜桃影像傳媒", "香蕉視頻傳媒", "星空無限傳媒", "天美傳媒",
        "精東影業", "杏吧傳媒", "91製片廠", "皇家華人", "起點傳媒",
        "果凍傳媒", "蘿莉社", "ED Mosaic", "兔子先生", "扣扣傳媒",
        "SA國際傳媒", "愛神傳媒", "性視界傳媒", "抖陰", "91茄子"
    ]
    tanhua_tags = [
        "小寶尋花", "午夜尋花", "千人斬探花", "七天探花", "大神精選",
        "91沈先生", "調教小景甜", "91lisa", "91鳳鳴鳥唱", "91貓先生",
        "全國探花", "91Fans", "9總全國探花", "鴨哥探花", "錘子探花",
        "探花合集", "91不見星空", "91康先生"
    ]
    zipai_tags = [
        "調教小景甜", "91沈先生", "91lisa", "91鳳鳴鳥唱", "91不見星空",
        "91康先生", "18歲母狗無限高潮", "肉オナホ"
    ]
    madou_tags = [
        "愛豆傳媒", "MD", "MDX", "麻豆US", "MSD", "MCY", "MKY", "MPG",
        "FLIXKO", "貓爪影像", "國產麻豆AV節目", "麻豆女神微愛視頻", "麻豆番外",
        "麻豆三十天特別企劃", "麻豆導演系列", "麻豆女優", "澀會"
    ]
    onlyfans_tags = [
        "HongKongDoll", "BunnyMiffy", "Nana_Taipei", "qiobnxingcai",
        "suchanghub", "ssrpeach", "Miuzxc", "yui_xin_tw", "kitty2002102",
        "fansly", "tangbo_hu", "juneliu", "YuZuKitty"
    ]
    japan_tags = [
        "中文字幕", "單體作品", "中出", "巨乳", "熟女", "人妻", "絲襪",
        "NTR", "美少女", "口交", "痴女", "fc2 ppv", "my amateur-z"
    ]
    series_tags = [
        "AI短劇", "角色劇情", "現代", "都市", "大男主", "後宮", "劇情"
    ]
    hot_v_tags = [
        "自拍流出", "國產AV", "探花", "日本", "麻豆傳媒", "OnlyFans",
        "中文字幕", "單體作品", "巨乳", "熟女", "人妻", "絲襪", "NTR", "美少女", "糖心Vlog"
    ]

    def _sub(tid, name):
        return {"tid": tid, "name": name}

    def _tag_subs(tags):
        return [_sub(f"t/{t}", t) for t in tags]

    return [
        {
            "tid": "v",
            "name": "影片庫",
            "subcategories": [_sub("v", "全部影片")] + _tag_subs(hot_v_tags),
        },
        {
            "tid": "t/國產AV",
            "name": "國產AV",
            "subcategories": [_sub("t/國產AV", "全部國產AV")] + _tag_subs(guocan_tags),
        },
        {
            "tid": "t/探花",
            "name": "探花",
            "subcategories": [_sub("t/探花", "全部探花")] + _tag_subs(tanhua_tags),
        },
        {
            "tid": "t/自拍流出",
            "name": "自拍流出",
            "subcategories": [_sub("t/自拍流出", "全部自拍流出")] + _tag_subs(zipai_tags),
        },
        {
            "tid": "t/麻豆傳媒",
            "name": "麻豆傳媒",
            "subcategories": [_sub("t/麻豆傳媒", "全部麻豆傳媒")] + _tag_subs(madou_tags),
        },
        {
            "tid": "t/OnlyFans",
            "name": "OnlyFans",
            "subcategories": [_sub("t/OnlyFans", "全部OnlyFans")] + _tag_subs(onlyfans_tags),
        },
        {
            "tid": "t/日本",
            "name": "日本",
            "subcategories": [_sub("t/日本", "全部日本")] + _tag_subs(japan_tags),
        },
        {
            "tid": "series",
            "name": "劇集庫",
            "subcategories": [_sub("series", "全部劇集")] + _tag_subs(series_tags),
        },
    ]


def _series_id(root) -> str:
    """详情页里的劇集 id（面包屑或劇集卡片的 ``/s/<cuid>``）。"""
    matched = _ITEM_HREF_RE.match((root.select_first('a[href^="/s/"]') or {}).attr("href") or "")
    if matched and matched.group(1) == "s":
        return matched.group(2)
    return ""


def _episode_row(anchor):
    """一行剧集 → ``(ep_index, ep_name)``；不是剧集行返回 ``None``。

    两套标记（实测，影片页与劇集页不同，别只写一套）：

    * 影片页：列表行，序号在 ``span.tabular-nums``（``01``）、集名在 ``span.truncate``；
    * 劇集页：宫格块 ``a.text-center``，文本本身就是「第 N 集」（旁边 small 是时长）。

    相关推荐卡片两者都不满足（它们只有时长角标）—— 这就是剧集行与推荐卡片的边界。
    """
    for span in anchor.select("span"):
        if "tabular-nums" in span.class_list:
            index = clean.to_int(span.text)
            name = ""
            for row in anchor.select("span"):
                if "truncate" in row.class_list and clean.collapse(row.text):
                    name = clean.collapse(row.text)
                    break
            return index, name
    if "text-center" in anchor.class_list:
        matched = _EP_INDEX_RE.search(clean.collapse(anchor.text))
        if matched:
            return clean.to_int(matched.group(1)), f"第{matched.group(1)}集"
    return None


def _episodes(root) -> list:
    """剧集行 → episodes（``ep_index`` 1 起算）。"""
    out = []
    for anchor in root.select('a[href^="/v/"]'):
        row = _episode_row(anchor)
        if row is None:
            continue
        index, name = row
        if index is None or index < 1:
            index = len(out) + 1

        matched = _ITEM_HREF_RE.match(anchor.attr("href") or "")
        if not matched:
            continue
        out.append(
            {
                "ep_index": index,
                "ep_name": clean.strip_promo(name) or f"第{index}集",
                # 本源一集就是一个 video_id，播放地址只由它决定
                "play_id": matched.group(2),
                "line": 1,
            }
        )
    out.sort(key=lambda item: item["ep_index"])
    return clean.dedupe(out, key=lambda item: item["ep_index"])


def _declared_episodes(root) -> int:
    """劇集卡片上的「共 N 集」；拿不到返回 0。

    取**最小的那个容器**的命中：页面里可能同时挂着别的劇集卡片，
    外层大容器的文本会把它们的数字也算进来。
    """
    best = None
    for node in root.select("div"):
        matched = _TOTAL_EP_RE.search(node.text or "")
        if not matched:
            continue
        found = clean.to_int(matched.group(1), 0) or 0
        if not found:
            continue
        weight = len(node.text or "")
        if best is None or weight < best[0]:
            best = (weight, found)
    return best[1] if best else 0


# --------------------------------------------------------------------- 站点


class 首頁Crawler:
    """rou.video（肉視頻）单文件采集器。"""

    @staticmethod
    def decode_media(content: bytes) -> bytes | None:
        """媒体解封装钩子（供后端流代理 / 前端播放器调用，见 :func:`decode_media`）。"""
        return decode_media(content)

    key = KEY
    name = NAME
    #: 语义化版本号；后台覆盖部署时支持自动 patch 递增
    version = VERSION
    #: 契约要求的 base_url（本源在系统里的入口就是首页）
    base_url = BASE_URL
    #: direct = 播放器直连源站；proxy = 需后端中继。
    #: 本源必须是 proxy：清单与分片都被伪装成 PNG（见模块 docstring），
    #: 直连播放器拿到的是「image/png」，必须经中继解封装。
    mode = "proxy"
    capabilities = ("meta", "home", "category", "detail", "play")

    def __init__(self, client=None):
        #: Client 的 base_url 必须是 origin（不能是 /home，否则相对路径会被拼错）
        self.http = client or Client(
            base_url=SITE,
            timeout=15.0,
            retries=1,
            headers={
                "User-Agent": DEFAULT_UA,
                "Referer": SITE + "/home",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            min_interval=MIN_REQUEST_INTERVAL,
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
    def _check_target(id) -> tuple:
        """``id`` → ``(kind, cuid)``；``kind`` 是 ``v``（影片）或 ``s``（劇集）。"""
        text = str(id or "").strip().strip("/")
        normalized = text[2:] if text.startswith("s/") else text
        if not _CUID_RE.match(normalized):
            raise CrawlerError("NOT_FOUND", f"无效的影片 id: {id}")
        return ("s" if text.startswith("s/") else "v"), normalized

    @staticmethod
    def _check_tid(tid) -> str:
        value = str(tid or "").strip().strip("/")
        if not value or ".." in value or "\\" in value or not _TID_RE.match(value):
            raise CrawlerError("NOT_FOUND", f"无效的分类 id: {tid}")
        return value

    @staticmethod
    def _tid_path(tid: str, page: int) -> str:
        """分类 tid → 站内列表路径（三张列表页的形态实测得）。"""
        if tid == "v":
            path = "/v"
        elif tid == "series":
            path = "/series"
        else:  # t/<標籤>
            tag = urllib.parse.quote(tid[2:], safe="")
            path = f"/t/{tag}"
        return path if page <= 1 else f"{path}?page={page}"

    def _play_id_target(self, play_id) -> str:
        """``play_id`` → video_id；认 ``<cuid>`` 与 ``<cuid>|<line>|<ep>``，其余丢弃。"""
        text = str(play_id or "").strip()
        if not text:
            return ""
        head = text.split("|", 1)[0].strip()
        if _CUID_RE.match(head):
            return head
        log.warn(f"忽略不可信的 play_id（不是 cuid 或 cuid|line|ep）: {text[:80]!r}")
        return ""

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
                "TanStack Start SSR；列表 /v?page=N、/series?page=N、/t/<標籤>?page=N（每页 26）；"
                "详情 /v/<cuid>、劇集 /s/<cuid>；播放入口 /api/hls/<cuid> 302 到 CDN 的"
                "伪 PNG 清单（PNG 头 + 'roUd' zlib chunk），分片同样是伪装 .png 的裸 TS —— "
                "所以 mode=proxy，中继必须调 decode_media 解封装；封面是普通 JPEG，无需解密"
            ),
        }

    def home(self):
        """首页：多维分类树（8大核心一级分类 + 真实二级片商/标籤）+ 推荐片单。"""
        root = parse.parse_html(self._page("/home"))
        categories = _build_rou_categories()
        recommend = _cards(root)
        log.debug(f"home: {len(categories)} 个一级分类，{len(recommend)} 条推荐")
        return {"categories": categories, "recommend": recommend}

    def category(self, tid, page=1):
        """分类 / 標籤 / 劇集列表（分页）。"""
        value = self._check_tid(tid)
        current = max(1, clean.to_int(page, 1) or 1)
        root = parse.parse_html(self._page(self._tid_path(value, current)))
        videos = _cards(root)
        has_more = _total_pages(root) > current
        log.debug(f"category {value} page={current}: {len(videos)} 条，has_more={has_more}")
        return {"videos": videos, "page": current, "has_more": has_more}

    def detail(self, id):
        """详情 + 线路 + 逐集定位符。"""
        kind, cuid = self._check_target(id)
        html = self._page(f"/{kind}/{cuid}")
        root = parse.parse_html(html)

        name = ""
        heading = root.select_first("h1")
        if heading is not None:
            name = clean.strip_promo(heading.text)
        if not name:
            og_title = root.select_first('meta[property="og:title"]')
            raw_title = og_title.attr("content") if og_title is not None else ""
            name = clean.strip_promo(str(raw_title).split(" - ", 1)[0])
        if not name:
            raise CrawlerError("PARSE_ERROR", f"详情页没有解析到片名: {id}")

        poster = root.select_first('meta[property="og:image"]')
        description = root.select_first('meta[property="og:description"]')

        series_id = _series_id(root)
        episodes = _episodes(root)
        declared = _declared_episodes(root)
        if series_id and declared and len(episodes) < declared:
            # 详情页的劇集列表被截断时退回劇集页（实测 /s/<id> 会列全，无分页）
            log.debug(f"劇集列表只给了 {len(episodes)}/{declared} 集，改从 /s/{series_id} 取全")
            episodes = _episodes(parse.parse_html(self._page(f"/s/{series_id}")))

        if kind == "s" and episodes:
            # 劇集入口：备注给总数（实测劇集页就是「全 N 集」语义）
            remarks = f"全 {declared or len(episodes)} 集"
        elif episodes:
            current = next(
                (item for item in episodes if item["play_id"] == cuid),
                episodes[0],
            )
            index = current["ep_index"]
            remarks = f"第 {index} 集 / 全 {len(episodes)} 集" if len(episodes) > 1 else current["ep_name"]
        else:
            # 单片/劇集页没有剧集行时，至少把当前这一集保住
            episodes = [
                {"ep_index": 1, "ep_name": name, "play_id": cuid, "line": 1}
            ]
            remarks = ""

        video = {
            "vod_id": cuid if kind == "v" else f"s/{cuid}",
            "vod_name": name,
            "vod_pic": clean.absolute(
                poster.attr("content") if poster is not None else "", SITE
            ),
            "vod_remarks": clean.strip_promo(remarks),
        }

        tags = _detail_tags(root)
        if tags:
            video["vod_type"] = ",".join(tags)

        state = _state_video(html)
        if state.get("year"):
            video["vod_year"] = state["year"]
        if state.get("duration"):
            video["vod_duration"] = state["duration"]
        # 站点没有演员/导演/地区字段：不编造（见模块 docstring）

        description_text = clean.strip_promo(
            description.attr("content") if description is not None else ""
        )
        if " · " in description_text:
            head, tail = description_text.rsplit(" · ", 1)
            if len(tail) <= 24 and ("集" in tail or tail in name):
                description_text = head

        # 播放信令 ev:{d,k} 里就是站点自己给的播放入口与缩略图雪碧图；
        # 解不出来不影响详情（play 自己也能拼出同一个入口），所以失败只记日志
        try:
            signal = _play_signal(html)
        except CrawlerError as exc:
            signal = {}
            log.warn(f"播放信令解析失败（不影响详情）: {exc.message}")

        line = {
            "id": "1",
            "name": LINE_NAME,
            "episodes": episodes,
            # 另外两个键是给本系统后端 DetailPayload.lines（LineInfo）用的，多余键会被忽略
            "line": 1,
            "count": len(episodes),
        }
        payload = {
            "video": video,
            "desc": description_text,
            "lines": [line],
            # 顶层 episodes 是后端契约的平铺形状（带 line），与 lines[].episodes 同源
            "episodes": episodes,
            "series_id": series_id,
        }
        if signal.get("videoUrl"):
            payload["play_entry"] = clean.absolute(str(signal["videoUrl"]), SITE)
        if signal.get("thumbVTTUrl"):
            # 预览缩略图雪碧图的 WEBVTT（前端悬停预览用）；中继同样要解封装
            payload["thumb_vtt"] = clean.absolute(str(signal["thumbVTTUrl"]), SITE)
        return payload

    def play(self, id=None, ep=1, play_id=None, line=1):
        """取真实播放地址（站点入口现签，**不可缓存**）。

        三条入口，全都只落到同一个 ``/api/hls/<video_id>``：

        * ``--play-id <该集的 cuid>``：详情里每集都带着它，最快，零额外请求；
        * ``--id <cuid>``：单片、或劇集某一集自己的 id；
        * ``--id s/<劇集 id> --ep N``：劇集入口 + 集号，回详情页解析出第 N 集的 cuid（慢路径）。
        """
        line_no = max(1, clean.to_int(line, 1) or 1)
        if line_no > 1:
            log.warn(f"该源只有一条线路，忽略 --line {line_no}")

        target = self._play_id_target(play_id)
        if not target and id is not None:
            kind, cuid = self._check_target(id)
            if kind == "s" or (clean.to_int(ep, 1) or 1) > 1:
                # 慢路径：劇集入口或指定集号时，回详情页把这一集的 cuid 解析出来
                detail = self.detail(id)
                index = max(1, clean.to_int(ep, 1) or 1)
                item = next(
                    (row for row in detail["episodes"] if row["ep_index"] == index),
                    None,
                )
                if item is None:
                    raise CrawlerError(
                        "NOT_FOUND",
                        f"第 {index} 集不存在（共 {len(detail['episodes'])} 集）",
                    )
                target = item["play_id"]
            else:
                target = cuid

        if not target:
            raise CrawlerError(
                "NOT_FOUND",
                "play 需要 --id（cuid 或 s/<cuid>）或 --play-id（详情里每集都带）",
            )

        # 站点入口：302 到 CDN 上带 exp/auth 的清单地址，每次现签
        entry = f"{SITE}/api/hls/{target}"
        response = self.http.get(f"/api/hls/{target}")
        body = response.body if response.ok else b""
        payload = decode_media(body)
        if payload is None and body.startswith(b"#EXTM3U"):
            payload = body  # 站点哪天不再伪装，照样能播

        if payload is None:
            # 兜底：按详情页 ev 信令里**站点自己给**的地址再取一次
            # （入口哪天换形状时，这里能自己找到新地址，而不是直接报错）
            signal = _play_signal(self._page(f"/v/{target}"))
            declared = clean.absolute(str(signal.get("videoUrl") or ""), SITE)
            if declared and declared != entry:
                log.warn(f"/api/hls 入口失效（HTTP {response.status}），改按 ev 信令取 {declared}")
                response = self.http.get(declared)
                if not response.ok:
                    raise CrawlerError(
                        "HTTP_ERROR", f"{declared} 返回 HTTP {response.status}"
                    )
                body = response.body
                payload = decode_media(body) or (body if body.startswith(b"#EXTM3U") else None)

        if not response.ok:
            raise CrawlerError("HTTP_ERROR", f"播放清单返回 HTTP {response.status}: {entry}")
        if payload is None:
            raise CrawlerError(
                "PARSE_ERROR",
                f"播放清单不是可识别的内容（{len(body)} 字节，"
                f"Content-Type={response.headers.get('content-type')}）: {entry}",
            )

        text = payload.decode("utf-8", "replace")
        if not text.startswith("#EXTM3U"):
            raise CrawlerError("PARSE_ERROR", f"/api/hls/{target} 解封装后不是 m3u8 清单")

        segments = [row for row in text.splitlines() if row.strip() and not row.startswith("#")]
        log.debug(
            f"play {target}: 解出 {len(segments)} 个分片，首个分片 "
            f"{(segments[0] if segments else '')[:96]}"
        )

        return {
            "url": entry,
            "format": "m3u8",
            "headers": {
                "Referer": f"{SITE}/v/{target}",
                "User-Agent": DEFAULT_UA,
            },
            # 以下是给本系统中继/排查用的扩展字段（多余键会被忽略）：
            # url 每次现取、302 到签名的 CDN 地址，且响应是伪装 PNG，播放前必须 decode_media 解封装
            "wrapper": "png-roUd",
            "decoded_type": "mpegts" if payload[:1] == b"\x47" else "playlist",
            "segment_count": len(segments),
            "cacheable": False,
        }


#: 给不习惯中文类名的调用方留一个 ASCII 别名
RouCrawler = 首頁Crawler


if __name__ == "__main__":
    cli.main(首頁Crawler())
