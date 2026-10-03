"""引擎与基础工具离线单元测试。"""

from crawler.service.core.cleaner import (
    safe_resolve_url,
    strip_decorated_ad_words,
)
from crawler.service.core.gates import solve_cdndefend_cookie
from crawler.service.engine.extractor_html import extract_html_field, parse_html
from crawler.service.engine.extractor_json import extract_json_field
from crawler.service.engine.models import ExtractorType, FieldExtractor


def test_cleaner_strip_decorated():
    # 测试数学粗体等变体字符广告清洗
    raw = "𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞 最糟糕的初恋 𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞"
    cleaned = strip_decorated_ad_words(raw)
    assert cleaned == "最糟糕的初恋"


def test_cleaner_strip_emojis():
    from crawler.service.core.cleaner import clean_title, strip_emojis
    raw = "18+ 🔞 - 肉视频 ⚡🤖"
    assert strip_emojis(raw) == "18+  - 肉视频 "
    assert clean_title(raw) == "18+ - 肉视频"


def test_cleaner_safe_resolve_url():
    base = "https://example.com/site/"
    # 绝对路径
    assert safe_resolve_url(base, "/play/1.html") == "https://example.com/play/1.html"
    # 相对路径
    assert safe_resolve_url(base, "detail/2.html") == "https://example.com/site/detail/2.html"
    # 协议相对路径
    assert safe_resolve_url(base, "//cdn.com/stream.m3u8") == "https://cdn.com/stream.m3u8"
    # 外部完整绝对路径
    assert safe_resolve_url(base, "https://cdn2.com/video.m3u8") == "https://cdn2.com/video.m3u8"


def test_html_parser_and_css_selectors():
    html = """
    <div class="container" id="main">
        <h1 class="title">测试剧目</h1>
        <ul class="playlist">
            <li class="item" data-id="101"><a href="/play/1.html">第 1 集</a></li>
            <li class="item" data-id="102"><a href="/play/2.html">第 2 集</a></li>
        </ul>
        <div class="video-info">
            <img src="/img/cover.jpg" data-src="/img/real.jpg" alt="封面"/>
        </div>
    </div>
    """
    root = parse_html(html)

    # 1. 简单选择器
    title_node = root.select_first(".title")
    assert title_node is not None
    assert title_node.text == "测试剧目"

    # 2. 嵌套子代与属性选择
    links = root.select(".playlist > li.item a")
    assert len(links) == 2
    assert links[0].attr("href") == "/play/1.html"
    assert links[0].text == "第 1 集"

    # 3. 属性选择器 [data-id=102]
    item2 = root.select_first("[data-id=102]")
    assert item2 is not None

    # 4. 字段提取与正则二次提纯
    rule = FieldExtractor(
        type=ExtractorType.CSS,
        selector=".playlist li a",
        attribute="href",
        regex=r"/play/(\d+)\.html",
    )
    val = extract_html_field(root, rule, base_url="https://test.com")
    assert val == "1"


def test_json_extractor():
    sample_json = {
        "code": 200,
        "data": {
            "title": "短剧大结局",
            "count": 10,
            "episodes": [
                {"ep": 1, "m3u8": "stream/ep1.m3u8"},
                {"ep": 2, "m3u8": "stream/ep2.m3u8"},
            ],
        },
    }

    # 点分访问
    rule_title = FieldExtractor(selector="data.title")
    assert extract_json_field(sample_json, rule_title) == "短剧大结局"

    # 模板拼接
    rule_tpl = FieldExtractor(selector="data.count", template="全{value}集")
    assert extract_json_field(sample_json, rule_tpl) == "全10集"

    # 索引提取
    rule_ep2 = FieldExtractor(selector="data.episodes[1].m3u8", template="https://cdn.com/{value}")
    assert extract_json_field(sample_json, rule_ep2) == "https://cdn.com/stream/ep2.m3u8"


def test_cdndefend_challenge_solver():
    # 模拟真实 cdndefend 挑战页 HTML
    challenge_html = """
    <html><head><script>
    var c = 'd41d8cd98f00b204e9800998ecf8427e';
    var n1 = parseInt('0x' + c[0]);
    </script></head><body>checking...</body></html>
    """
    res = solve_cdndefend_cookie(challenge_html)
    assert res is not None
    assert "cdndefend_js_cookie" in res
    assert res["cdndefend_js_cookie"].startswith("d41d8cd98f00b204e9800998ecf8427e")
