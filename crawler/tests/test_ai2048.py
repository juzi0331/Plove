"""2048ai.vip 爬虫的离线测试：打的是 fixtures 里的真实结构快照，不联网。

运行：``python -m unittest discover -s tests -t .``（在 crawler/ 目录下）
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import cli  # noqa: E402
from crawler_kit.errors import CrawlerError  # noqa: E402
from sites.ai2048 import Ai2048  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "ai2048")

#: 按前缀匹配，**长的必须排在前面**
ROUTES = (
    ("/api/v1/short-dramas/home", "home.json", 200),
    ("/api/v1/short-dramas/249", "detail.json", 200),
    ("/api/v1/short-dramas", "list.json", 200),
    ("/api/v1/categories", "categories.json", 200),
)


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = payload
        self.body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.headers = {"content-type": "application/json; charset=utf-8"}
        self.url = "fake://"

    @property
    def ok(self):
        return 200 <= self.status < 300

    @property
    def text(self):
        return self.body.decode("utf-8")

    def json(self):
        return self.payload


class FakeClient:
    """按路径前缀返回预置响应，并记录每次调用的参数。"""

    def __init__(self, routes=ROUTES, override=None):
        self.routes = routes
        self.override = override or {}
        self.calls = []

    def get(self, url, params=None, headers=None):
        params = dict(params or {})
        self.calls.append((url, params))
        if url in self.override:
            payload, status = self.override[url]
            return FakeResponse(payload, status)
        for prefix, name, status in self.routes:
            if url.startswith(prefix):
                return FakeResponse(load(name), status)
        return FakeResponse({"code": 404, "message": "not found", "data": None}, 404)

    def last_params(self):
        return self.calls[-1][1]


def make_site(**kwargs):
    return Ai2048(client=FakeClient(**kwargs))


class MetaTests(unittest.TestCase):
    def test_meta_shape(self):
        meta = make_site().meta()
        for key in ("key", "name", "version", "base_url", "mode"):
            self.assertIn(key, meta)
        self.assertEqual(meta["mode"], "direct")
        self.assertIn("home", meta["capabilities"])
        self.assertNotIn("search", meta["capabilities"])


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.home = make_site().home()

    def test_sections(self):
        titles = [section["title"] for section in self.home["sections"]]
        self.assertEqual(titles, ["热播推荐", "追剧榜", "精选短剧"])

    def test_bad_rows_are_dropped(self):
        # featured 里塞了两条坏数据（无 id / 标题全空白），必须被丢掉
        featured = next(s for s in self.home["sections"] if s["title"] == "精选短剧")
        self.assertEqual([v["vod_id"] for v in featured["videos"]], ["200"])

    def test_recommend_deduped(self):
        ids = [v["vod_id"] for v in self.home["recommend"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, ["249", "248", "176", "200"])

    def test_vod_item_required_fields(self):
        expected = {"249": "全7集", "248": "全5集", "176": "全5集", "200": "全1集"}
        for video in self.home["recommend"]:
            for key in ("vod_id", "vod_name", "vod_pic", "vod_remarks"):
                self.assertIn(key, video)
            self.assertTrue(video["vod_pic"].startswith("https://"))
            self.assertEqual(video["vod_remarks"], expected[video["vod_id"]])

    def test_zero_rating_is_omitted_not_faked(self):
        # fixture 里 id=200 的 rating 是 0，属于"源站没有评分"，不应写入
        featured = next(s for s in self.home["sections"] if s["title"] == "精选短剧")
        self.assertNotIn("vod_score", featured["videos"][0])

    def test_vod_item_mapping(self):
        first = self.home["recommend"][0]
        self.assertEqual(first["vod_id"], "249")
        self.assertEqual(first["vod_name"], "2048原创短剧 - 我是爸爸的新妻子")
        self.assertEqual(
            first["vod_pic"],
            "https://2048ai.vip/uploads/images/7baf35bba6cd4e688cbf733faf3d9406.jpg",
        )
        self.assertEqual(first["vod_remarks"], "全7集")
        self.assertEqual(first["vod_year"], 2026)
        self.assertEqual(first["vod_score"], 9.4)
        self.assertEqual(first["vod_type"], "原创,都市")

    def test_categories_filtered(self):
        tids = [c["tid"] for c in self.home["categories"]]
        self.assertEqual(tids, ["27", "1"])  # 下线的、别的产品线都被过滤


class CategoryTests(unittest.TestCase):
    def test_category_mapping_and_paging(self):
        site = make_site()
        result = site.category(tid="27", page=1)
        self.assertEqual(len(result["videos"]), 2)
        self.assertEqual(result["page"], 1)
        self.assertTrue(result["has_more"])  # totalPages=20
        self.assertEqual(site.http.last_params()["categoryId"], "27")
        self.assertEqual(site.http.last_params()["sortBy"], "heat")

    def test_category_without_tid(self):
        site = make_site()
        site.category()
        self.assertNotIn("categoryId", site.http.last_params())

    def test_last_page_has_no_more(self):
        payload = load("list.json")
        payload["data"]["page"] = 20
        site = make_site(
            override={"/api/v1/short-dramas": (payload, 200)}
        )
        self.assertFalse(site.category(page=20)["has_more"])


class DetailTests(unittest.TestCase):
    def setUp(self):
        self.detail = make_site().detail(id="249")

    def test_episodes_sorted_and_cleaned(self):
        episodes = self.detail["episodes"]
        self.assertEqual([e["ep_index"] for e in episodes], [1, 2, 3, 7])
        self.assertEqual(episodes[0]["play_id"], "20562")
        self.assertEqual(episodes[0]["duration_sec"], 262)

    def test_empty_title_falls_back(self):
        second = next(e for e in self.detail["episodes"] if e["ep_index"] == 2)
        self.assertEqual(second["ep_name"], "第2集")

    def test_desc_promo_stripped(self):
        self.assertEqual(self.detail["desc"], "我是爸爸的新妻子")

    def test_missing_id_raises_not_found(self):
        site = make_site(override={"/api/v1/short-dramas/249": ({"code": 200, "message": "ok", "data": None}, 200)})
        with self.assertRaises(CrawlerError) as ctx:
            site.detail(id="249")
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


class PlayTests(unittest.TestCase):
    def test_play_builds_proxy_url(self):
        result = make_site().play(id="249", ep=1)
        self.assertEqual(result["format"], "m3u8")
        self.assertTrue(result["url"].startswith("https://2048ai.vip/api/v1/m3u8/proxy?path="))
        # 相对路径必须被整体 urlencode（斜杠也要编码），否则站点拿不到
        self.assertIn("%2F", result["url"])
        self.assertIn("430846dc47884812bbebfb601e8e15e8.m3u8", result["url"])
        self.assertNotIn("jpd/", result["url"])

    def test_play_missing_episode(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().play(id="249", ep=99)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_play_episode_without_url(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().play(id="249", ep=3)
        self.assertEqual(ctx.exception.code, "PARSE_ERROR")

    def test_play_never_uses_trailer(self):
        """列表里的 previewVideoUrl 是预告片，绝不能当成正片。"""
        result = make_site().play(id="249", ep=1)
        self.assertNotIn("trailer", result["url"])

    def test_play_accepts_string_ep(self):
        self.assertEqual(
            make_site().play(id="249", ep="7")["format"], "m3u8"
        )


class ErrorTests(unittest.TestCase):
    def test_business_code_not_200(self):
        site = make_site(
            override={"/api/v1/short-dramas": ({"code": 500, "message": "内部错误", "data": None}, 200)}
        )
        with self.assertRaises(CrawlerError) as ctx:
            site.category()
        self.assertEqual(ctx.exception.code, "HTTP_ERROR")

    def test_http_404(self):
        site = make_site(override={"/api/v1/short-dramas": ({"code": 404, "message": "no", "data": None}, 404)})
        with self.assertRaises(CrawlerError) as ctx:
            site.category()
        self.assertEqual(ctx.exception.code, "HTTP_ERROR")

    def test_search_is_unsupported(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().search(kw="x")
        self.assertEqual(ctx.exception.code, "UNSUPPORTED")

    def test_selftest_fingerprint(self):
        site = make_site()
        fingerprint = site.selftest()["selectors"]
        # fixture 不理会 size=1，所以 items 是快照里的 2 条
        self.assertEqual(fingerprint["list.items"], 2)
        self.assertEqual(fingerprint["list.total"], 480)
        self.assertEqual(fingerprint["home.banner"], 2)
        self.assertEqual(fingerprint["home.featured"], 3)
        self.assertEqual(fingerprint["categories"], 2)
        # 自检必须真的发请求，而不是读缓存
        self.assertEqual(site.http.last_params()["type"], "video")


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.run(make_site(), argv)
        lines = buffer.getvalue().strip().splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 1, f"stdout 只允许一行 JSON，实际 {lines!r}")
        return json.loads(lines[0])

    def test_success_envelope(self):
        payload = self.run_cli(["home"])
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["error"])
        self.assertIn("sections", payload["data"])

    def test_unsupported_envelope(self):
        payload = self.run_cli(["search", "--kw", "测试"])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "UNSUPPORTED")

    def test_missing_required_arg(self):
        payload = self.run_cli(["detail"])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.assertIn("--id", payload["error"]["message"])

    def test_unknown_command(self):
        payload = self.run_cli(["frobnicate"])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "UNSUPPORTED")

    def test_page_flag_coerced_to_int(self):
        site = make_site()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cli.run(site, ["category", "--tid", "27", "--page", "2"])
        self.assertEqual(site.http.last_params()["page"], 2)

    def test_unexpected_exception_still_returns_envelope(self):
        class Boom(Ai2048):
            def home(self):
                raise RuntimeError("炸了")

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.run(Boom(client=FakeClient()), ["home"])
        payload = json.loads(buffer.getvalue().strip())
        self.assertEqual(code, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
