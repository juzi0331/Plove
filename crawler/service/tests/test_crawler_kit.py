"""crawler_kit 的单元测试：清洗、解析、HTTP 客户端（离线运行）。"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time
import unittest

from crawler.crawler_kit import clean, parse
from crawler.crawler_kit.errors import CrawlerError
from crawler.crawler_kit.http import Client

SAMPLE_HTML = """
<html><body>
<div class="episode-list-box">
  <div class="episode-list-box-main">
    <div class="episode-list">
      <a href="/play/318185-41-2946527.html" class="episode-item" data-index="1"><span>1080P</span></a>
      <a href="/play/318185-41-2946528.html" class="episode-item" data-index="2"><span>HD国语</span></a>
    </div>
  </div>
</div>
<div id="main">
  <p class="v-item-title">第一集</p>
  <p class="v-item-title">第二集</p>
  <ul><li>甲</li><li>乙</li></ul>
</div>
<script>var u = "https:\\/\\/8.97.228:21302\\/a\\/b\\/index.m3u8?sign=1";</script>
</body></html>
"""


class CleanTests(unittest.TestCase):
    def test_absolute(self):
        self.assertEqual(
            clean.absolute("/uploads/a.jpg", "https://example.com"),
            "https://example.com/uploads/a.jpg",
        )
        self.assertEqual(
            clean.absolute("//cdn.x/a.jpg", "https://example.com"),
            "https://cdn.x/a.jpg",
        )
        self.assertEqual(
            clean.absolute("bbb.jpg", "https://example.com"),
            "https://example.com/bbb.jpg",
        )
        self.assertEqual(
            clean.absolute("https://cdn.example.com/b.jpg", "https://example.com"),
            "https://cdn.example.com/b.jpg",
        )
        self.assertEqual(clean.absolute("", "https://example.com"), "")

    def test_text_helpers(self):
        self.assertEqual(clean.clean_text("<p>你好<br>世界</p>"), "你好 世界")
        self.assertEqual(clean.clean_text("  <b>a</b>   b "), "a b")
        self.assertEqual(clean.clean_text(None), "")

    def test_numbers(self):
        self.assertEqual(clean.to_int("第7集"), 7)
        self.assertEqual(clean.to_int(None), None)
        self.assertEqual(clean.to_int("abc", 3), 3)
        self.assertEqual(clean.to_int(True, 9), 9)
        self.assertEqual(clean.to_float("9.4分"), 9.4)
        self.assertIsNone(clean.to_float(None))

    def test_quality_and_promo(self):
        self.assertEqual(clean.normalize_quality(" 1080p "), "1080P")
        self.assertEqual(clean.normalize_quality("超清"), "超清")
        self.assertEqual(clean.strip_promo("我是爸爸的新妻子  永久地址发布页"), "我是爸爸的新妻子")

    def test_strip_decorated_watermark(self):
        raw = "𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞 最糟糕的初恋 𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞"
        self.assertEqual(clean.strip_decorated(raw), "最糟糕的初恋")
        self.assertEqual(clean.strip_promo(raw), "最糟糕的初恋")
        self.assertEqual(clean.strip_decorated("第 1 集 · 1080P"), "第 1 集 · 1080P")
        self.assertEqual(clean.strip_decorated(""), "")

    def test_blocked_host(self):
        self.assertTrue(clean.is_blocked_host("https://t.me/xxx"))
        self.assertTrue(clean.is_blocked_host("https://sub.t.me/xxx"))
        self.assertFalse(clean.is_blocked_host("https://example.com/uploads/a.jpg"))
        self.assertTrue(clean.is_blocked_host(""))

    def test_safe_relative_path_keeps_site_local_paths(self):
        self.assertEqual(
            clean.safe_relative_path("/play/318185-41-2946527.html"),
            "/play/318185-41-2946527.html",
        )
        self.assertEqual(clean.safe_relative_path("  /a/b?c=1 "), "/a/b?c=1")

    def test_safe_relative_path_rejects_urls_that_escape_the_host(self):
        for bad in (
            "https://evil.example/x",
            "http://evil.example/x",
            "//evil.example/x",
            "\\\\evil.example\\x",
            "/a/../../../etc/passwd",
            "javascript:alert(1)",
            "",
            None,
        ):
            self.assertEqual(clean.safe_relative_path(bad), "", f"不该放行: {bad!r}")


class ParseTests(unittest.TestCase):
    def test_select_class_and_tag(self):
        self.assertEqual(len(parse.select(SAMPLE_HTML, ".v-item-title")), 2)
        self.assertEqual(len(parse.select(SAMPLE_HTML, "a.episode-item")), 2)
        self.assertEqual(len(parse.select(SAMPLE_HTML, "li")), 2)

    def test_child_and_descendant(self):
        self.assertEqual(len(parse.select(SAMPLE_HTML, ".episode-list > a")), 2)
        self.assertEqual(len(parse.select(SAMPLE_HTML, ".episode-list-box-main a")), 2)
        self.assertEqual(len(parse.select(SAMPLE_HTML, ".episode-list-box-main > a")), 0)

    def test_attribute_selector(self):
        self.assertEqual(len(parse.select(SAMPLE_HTML, "a[href^='/play/']")), 2)
        self.assertEqual(len(parse.select(SAMPLE_HTML, "a[data-index='2']")), 1)
        self.assertEqual(len(parse.select(SAMPLE_HTML, "a[data-index]")), 2)
        self.assertEqual(len(parse.select(SAMPLE_HTML, "a[href$='.html']")), 2)

    def test_id_selector(self):
        self.assertEqual(len(parse.select(SAMPLE_HTML, "#main p")), 2)
        self.assertEqual(len(parse.select(SAMPLE_HTML, "#nope")), 0)

    def test_attr_and_text(self):
        node = parse.select_one(SAMPLE_HTML, "a.episode-item")
        self.assertEqual(node.attr("data-index"), "1")
        self.assertEqual(node.text, "1080P")
        self.assertIn("1080P", parse.select_one(SAMPLE_HTML, ".episode-list-box").text)

    def test_implied_close(self):
        items = parse.select(SAMPLE_HTML, "#main li")
        self.assertEqual([item.text for item in items], ["甲", "乙"])

    def test_regex_helpers(self):
        self.assertEqual(parse.re_first(r"data-index=\"(\d+)\"", SAMPLE_HTML), "1")
        self.assertEqual(parse.re_all(r"data-index=\"(\d+)\"", SAMPLE_HTML), ["1", "2"])
        self.assertEqual(parse.re_first(r"不存在", SAMPLE_HTML, default="x"), "x")

    def test_find_m3u8(self):
        found = parse.find_m3u8(SAMPLE_HTML)
        self.assertIn("https://8.97.228:21302/a/b/index.m3u8?sign=1", found)
        bare = parse.find_m3u8('var u = "8.97.228:21302/data3/x/index.m3u8?appId=demo"')
        self.assertEqual(bare, ["8.97.228:21302/data3/x/index.m3u8?appId=demo"])
        self.assertEqual(parse.find_m3u8("<p>没有播放地址</p>"), [])

    def test_find_m3u8_preserves_query_entities(self):
        query = "?appId=n&timestamp=1790678284&sign=abc"
        found = parse.find_m3u8('<script>var u="https://cdn.x/a/index.m3u8%s"</script>' % query)
        self.assertEqual(found, ["https://cdn.x/a/index.m3u8" + query])
        self.assertNotIn(chr(0xD7), found[0])


ATTEMPTS = {"flaky": 0}
LOCK = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _reply(self, status, body: bytes, content_type="application/json; charset=utf-8", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/ok":
            self._reply(200, json.dumps({"code": 200, "data": [1, 2]}).encode())
        elif path == "/gate":
            self._reply(850, b"<html>Protected by cdndefend</html>", "text/html")
        elif path == "/flaky":
            with LOCK:
                ATTEMPTS["flaky"] += 1
                attempt = ATTEMPTS["flaky"]
            if attempt < 3:
                self._reply(500, b"boom", "text/plain")
            else:
                self._reply(200, b'{"code": 200, "data": "recovered"}')
        elif path == "/need-cookie":
            if "gate=1" in (self.headers.get("Cookie") or ""):
                self._reply(200, b'{"code": 200, "data": "passed"}')
            else:
                self._reply(
                    850,
                    b"challenge",
                    "text/html",
                    extra={"Set-Cookie": "gate=1; Path=/"},
                )
        else:
            self._reply(404, b"nope", "text/plain")


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._saved_proxy = {}
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "NO_PROXY", "no_proxy"):
            if k in os.environ:
                cls._saved_proxy[k] = os.environ.pop(k)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        for k, v in cls._saved_proxy.items():
            os.environ[k] = v

    def test_json_roundtrip(self):
        response = Client(base_url=self.base, backoff=0).get("/ok")
        self.assertTrue(response.ok)
        self.assertEqual(response.json()["data"], [1, 2])

    def test_non_standard_status_is_returned_not_raised(self):
        response = Client(base_url=self.base, retries=0, backoff=0).get("/gate")
        self.assertFalse(response.ok)
        self.assertEqual(response.status, 850)
        self.assertIn("cdndefend", response.text)

    def test_retry_on_5xx_then_succeed(self):
        with LOCK:
            ATTEMPTS["flaky"] = 0
        response = Client(base_url=self.base, retries=3, backoff=0).get("/flaky")
        self.assertTrue(response.ok)
        self.assertEqual(response.json()["data"], "recovered")
        self.assertGreaterEqual(ATTEMPTS["flaky"], 3)

    def test_4xx_is_not_retried(self):
        response = Client(base_url=self.base, retries=3, backoff=0).get("/missing")
        self.assertEqual(response.status, 404)

    def test_cookie_absorbed_and_replayed(self):
        client = Client(base_url=self.base, retries=0, backoff=0)
        first = client.get("/need-cookie")
        self.assertEqual(first.status, 850)
        self.assertEqual(client.cookies.get("gate"), "1")
        second = client.get("/need-cookie")
        self.assertTrue(second.ok)
        self.assertEqual(second.json()["data"], "passed")

    def test_timeout_maps_to_crawler_error(self):
        client = Client(base_url="http://127.0.0.1:9", retries=0, backoff=0, timeout=0.5)
        with self.assertRaises(CrawlerError) as ctx:
            client.get("/ok")
        self.assertEqual(ctx.exception.code, "TIMEOUT")

    def test_min_interval_throttles_requests(self):
        client = Client(base_url=self.base, backoff=0, min_interval=0.3)
        start = time.monotonic()
        client.get("/ok")
        client.get("/ok")
        self.assertGreaterEqual(time.monotonic() - start, 0.28)

    def test_json_parse_error(self):
        response = Client(base_url=self.base, backoff=0).get("/missing")
        with self.assertRaises(CrawlerError) as ctx:
            response.json()
        self.assertEqual(ctx.exception.code, "PARSE_ERROR")
