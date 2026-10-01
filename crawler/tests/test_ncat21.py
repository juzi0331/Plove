"""ncat21.com 的离线测试：含 cdndefend 闸门的完整流程，不联网。

运行：``python -m unittest discover -s tests -t .``（在 crawler/ 目录下）
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest

# 测试阶段不要被闸门日志刷屏（log 的级别在 import 时读取）
os.environ.setdefault("CRAWLER_LOG", "error")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_kit import cli  # noqa: E402
from crawler_kit.errors import CrawlerError  # noqa: E402
from sites.ncat21 import Ncat21, solve_cdndefend  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "ncat21")


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


CHALLENGE = load("challenge.html")
HOME = load("home.html")
DETAIL = load("detail.html")
PLAY = load("play.html")

COOKIE_NAME = "cdndefend_js_cookie"
COOKIE_VALUE = "A337D1EB9CCD6D599AE51019BD471B92F7245FE149882"

ROUTES = {
    "/": HOME,
    "/channel/1.html": HOME,
    "/detail/318185.html": DETAIL,
    "/detail/318186.html": DETAIL,
    "/play/318185-41-2946527.html": PLAY,
    "/play/318185-35-2946794.html": PLAY,
}


class FakeResponse:
    def __init__(self, text, status=200):
        self.status = status
        self.body = text.encode("utf-8")
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.url = "fake://"

    @property
    def ok(self):
        return 200 <= self.status < 300

    @property
    def text(self):
        return self.body.decode("utf-8")

    def json(self):
        return json.loads(self.text)


class FakeClient:
    """模拟 cdndefend 闸门：没有合法 cookie 就一律返回 850。"""

    def __init__(self, routes=None, require_cookie=True):
        self.routes = routes or ROUTES
        self.require_cookie = require_cookie
        self.cookies = {}
        self.calls = []
        self.drop_cookie_on = None

    def set_cookies(self, cookies):
        for key, value in (cookies or {}).items():
            self.cookies[str(key)] = str(value)

    def get(self, url, params=None, headers=None):
        self.calls.append(url)
        if self.drop_cookie_on is not None and len(self.calls) == self.drop_cookie_on:
            self.cookies.pop(COOKIE_NAME, None)
            self.drop_cookie_on = None
        if self.require_cookie and self.cookies.get(COOKIE_NAME) != COOKIE_VALUE:
            return FakeResponse(CHALLENGE, 850)
        path = url.split("?", 1)[0]
        entry = self.routes.get(path)
        if entry is None:
            return FakeResponse("<html>404</html>", 404)
        text, status = entry if isinstance(entry, tuple) else (entry, 200)
        return FakeResponse(text, status)


def make_site(client=None, **kwargs):
    return Ncat21(client=client or FakeClient(**kwargs))


class SolveTests(unittest.TestCase):
    def test_solver_reproduces_browser_cookie(self):
        self.assertEqual(solve_cdndefend(CHALLENGE), COOKIE_VALUE)

    def test_solver_rejects_page_without_secret(self):
        with self.assertRaises(CrawlerError) as ctx:
            solve_cdndefend("<html><body>nothing here</body></html>")
        self.assertEqual(ctx.exception.code, "BLOCKED")

    def test_solver_is_fast(self):
        import time

        start = time.time()
        solve_cdndefend(CHALLENGE)
        self.assertLess(time.time() - start, 5.0)


class GateTests(unittest.TestCase):
    def test_gate_is_solved_transparently(self):
        client = FakeClient()
        home = make_site(client).home()
        self.assertTrue(home["recommend"])
        self.assertEqual(client.cookies[COOKIE_NAME], COOKIE_VALUE)

    def test_cookie_is_cached_not_resolved_every_call(self):
        client = FakeClient()
        site = make_site(client)
        site.home()
        before = len(client.calls)
        site.home()
        # 已解且未过期，就只应有 1 次请求（不再探测/重解）
        self.assertEqual(len(client.calls) - before, 1)

    def test_gate_recovers_after_cookie_expiry(self):
        client = FakeClient()
        site = make_site(client)
        site.home()
        client.drop_cookie_on = len(client.calls) + 1
        home = site.home()
        self.assertTrue(home["recommend"])
        self.assertEqual(client.cookies[COOKIE_NAME], COOKIE_VALUE)

    def test_unexpected_status_is_blocked(self):
        # require_cookie=False：让探测直接拿到 403，而不是闸门的 850
        client = FakeClient({"/": ("<html>forbidden</html>", 403)}, require_cookie=False)
        with self.assertRaises(CrawlerError) as ctx:
            make_site(client).home()
        self.assertEqual(ctx.exception.code, "BLOCKED")


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.home = make_site().home()

    def test_categories_from_channel_links(self):
        self.assertEqual(
            [(c["tid"], c["name"]) for c in self.home["categories"]],
            [("1", "电影"), ("2", "连续剧")],
        )

    def test_only_detail_links_become_cards(self):
        self.assertEqual(
            [v["vod_id"] for v in self.home["recommend"]], ["318185", "318186"]
        )

    def test_name_skips_hidden_ad_watermark(self):
        self.assertEqual(self.home["recommend"][0]["vod_name"], "四渡")

    def test_cover_prefers_real_image_over_placeholder(self):
        pic = self.home["recommend"][0]["vod_pic"]
        self.assertNotIn("placeholder", pic)
        self.assertEqual(
            pic,
            "https://www.ncat21.com/vod1/vod/cover/20260814/23/02/41/"
            "883dc7eadc3a9152f13d30b3d67400df.jpg",
        )

    def test_card_without_cover_yields_empty_pic(self):
        self.assertEqual(self.home["recommend"][1]["vod_pic"], "")

    def test_remarks_and_type(self):
        first = self.home["recommend"][0]
        self.assertEqual(first["vod_remarks"], "更新至18集")
        self.assertEqual(first["vod_type"], "影片")

    def test_required_fields_present(self):
        for video in self.home["recommend"]:
            for key in ("vod_id", "vod_name", "vod_pic", "vod_remarks"):
                self.assertIn(key, video)


class CategoryTests(unittest.TestCase):
    def test_channel_path(self):
        client = FakeClient()
        result = make_site(client).category(tid="1", page=1)
        self.assertIn("/channel/1.html", client.calls[-1])
        self.assertTrue(result["videos"])
        self.assertTrue(result["has_more"])

    def test_page_query_appended(self):
        client = FakeClient()
        make_site(client).category(tid="1", page=3)
        self.assertIn("page=3", client.calls[-1])

    def test_invalid_tid(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().category(tid="abc")
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


class DetailTests(unittest.TestCase):
    def setUp(self):
        self.detail = make_site().detail(id="318185")

    def test_title_not_the_ad(self):
        self.assertEqual(self.detail["video"]["vod_name"], "四渡")

    def test_variant_letter_watermark_is_stripped(self):
        # .detail-title 里混了 𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞 这种变体字水印，必须清掉
        self.assertNotIn(chr(0x1D55C), self.detail["video"]["vod_name"])

    def test_desc_promo_stripped(self):
        self.assertEqual(
            self.detail["desc"], "四渡剧情：一支小队在渡口遭遇伏击。"
        )

    def test_cover_from_og_image(self):
        self.assertEqual(
            self.detail["video"]["vod_pic"],
            "https://www.ncat21.com/vod1/vod/cover/20260814/23/02/41/"
            "883dc7eadc3a9152f13d30b3d67400df.jpg",
        )

    def test_remarks(self):
        self.assertEqual(self.detail["video"]["vod_remarks"], "更新至18集")

    def test_lines(self):
        self.assertEqual(
            self.detail["lines"],
            [
                {"line": 1, "name": "线路1", "count": 2},
                {"line": 2, "name": "线路2", "count": 1},
            ],
        )

    def test_episodes_flattened_with_line(self):
        self.assertEqual(
            [(e["line"], e["ep_index"]) for e in self.detail["episodes"]],
            [(1, 1), (1, 2), (2, 1)],
        )

    def test_play_id_is_full_path_because_index_collides(self):
        """两条线路的第 1 集 data-index 都是 1，只有完整路径是唯一的。"""
        firsts = [e for e in self.detail["episodes"] if e["ep_index"] == 1]
        self.assertEqual(len(firsts), 2)
        self.assertNotEqual(firsts[0]["play_id"], firsts[1]["play_id"])
        for episode in self.detail["episodes"]:
            self.assertTrue(episode["play_id"].startswith("/play/"))

    def test_invalid_id(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().detail(id="四渡")
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


class PlayTests(unittest.TestCase):
    def test_picks_the_1080p_manifest_not_the_ad(self):
        result = make_site().play(id="318185", ep=1, line=1)
        self.assertEqual(result["format"], "m3u8")
        self.assertNotIn("ads.example.com", result["url"])
        self.assertIn("/1920/index.m3u8", result["url"])
        self.assertTrue(result["url"].startswith("https://8.97.228:21302/"))

    def test_query_string_survives(self):
        url = make_site().play(id="318185", ep=1, line=1)["url"]
        self.assertIn("appId=ncat", url)
        self.assertIn("sign=", url)
        self.assertIn("timestamp=", url)

    def test_play_page_fetched_for_the_right_line(self):
        client = FakeClient()
        make_site(client).play(id="318185", ep=1, line=2)
        self.assertEqual(client.calls[-1], "/play/318185-35-2946794.html")

    def test_play_id_skips_the_detail_request(self):
        """带上 play_id 就不该再去抓详情页 —— 那一次实测要 3.5 秒。"""
        client = FakeClient()
        result = make_site(client).play(play_id="/play/318185-41-2946527.html")

        self.assertEqual(client.calls[-1], "/play/318185-41-2946527.html")
        self.assertNotIn("/detail/318185.html", client.calls, "还在抓详情页，等于没优化")
        self.assertIn("/1920/index.m3u8", result["url"])

    def test_untrusted_play_id_falls_back_instead_of_fetching_it(self):
        """play_id 是上层回传的，属于信任边界：绝对 URL 会让我们变成任意地址的代理。"""
        for bad in ("https://evil.example/x", "//evil.example/x", "evil.example/x"):
            with self.subTest(bad=bad):
                client = FakeClient()
                result = make_site(client).play(id="318185", ep=1, line=1, play_id=bad)
                self.assertIn("/detail/318185.html", client.calls, "应该退回详情页那条路")
                self.assertFalse([c for c in client.calls if "evil.example" in c], "吹出去了")
                self.assertIn("/1920/index.m3u8", result["url"])

    def test_play_needs_either_id_or_play_id(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().play()
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_referer_header_provided(self):
        result = make_site().play(id="318185", ep=1, line=1)
        self.assertEqual(result["headers"]["Referer"], "https://www.ncat21.com/")

    def test_missing_episode(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().play(id="318185", ep=9, line=1)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_missing_line(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().play(id="318185", ep=1, line=7)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_play_page_without_m3u8(self):
        client = FakeClient(dict(ROUTES, **{"/play/318185-41-2946527.html": "<html>空页面</html>"}))
        with self.assertRaises(CrawlerError) as ctx:
            make_site(client).play(id="318185", ep=1, line=1)
        self.assertEqual(ctx.exception.code, "PARSE_ERROR")


class MetaTests(unittest.TestCase):
    def test_meta_declares_gate_and_capabilities(self):
        meta = make_site().meta()
        self.assertEqual(meta["mode"], "direct")
        self.assertIn("cdndefend", meta["note"])
        self.assertNotIn("search", meta["capabilities"])

    def test_search_is_unsupported(self):
        with self.assertRaises(CrawlerError) as ctx:
            make_site().search(kw="四渡")
        self.assertEqual(ctx.exception.code, "UNSUPPORTED")

    def test_selftest_fingerprint(self):
        fingerprint = make_site().selftest()["selectors"]
        self.assertEqual(fingerprint["home.channel"], 3)
        self.assertEqual(fingerprint["home.cover_img"], 3)
        self.assertEqual(fingerprint["home.title_node"], 6)
        self.assertEqual(fingerprint["detail.episode_group"], 2)
        self.assertEqual(fingerprint["detail.episode_item"], 3)
        self.assertEqual(fingerprint["home.card"], 3)


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.run(make_site(), argv)
        lines = buffer.getvalue().strip().splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 1)
        return json.loads(lines[0])

    def test_meta_envelope(self):
        payload = self.run_cli(["meta"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["key"], "ncat21")

    def test_play_with_line_and_ep_flags(self):
        payload = self.run_cli(["play", "--id", "318185", "--line", "1", "--ep", "1"])
        self.assertTrue(payload["ok"])
        self.assertIn("/1920/index.m3u8", payload["data"]["url"])

    def test_unsupported_search_envelope(self):
        payload = self.run_cli(["search", "--kw", "四渡"])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
