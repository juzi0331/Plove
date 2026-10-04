"""专门用于向外部 AI（如 ChatGPT、Claude、DeepSeek）提问的针对性 Prompt 生成器。

当遇到高难度站点（加密、混淆、特殊反爬、非标准接口）时，
将目标站侦察到的上下文与 Plove 严格的后端爬虫契约打包为专业提示词，
让外部 AI 能够直接输出 100% 符合本项目标准的单文件 Python 脚本。
"""

from __future__ import annotations

from typing import Any


def build_ai_crawler_prompt(
    target_url: str,
    site_name: str = "",
    site_key: str = "",
    html_preview: str = "",
    api_preview: str = "",
    difficulty_note: str = "",
    categories_tree: list[dict[str, Any]] | None = None,
    detail_fields: list[dict[str, Any]] | None = None,
) -> str:
    """合成针对外部顶级 AI (ChatGPT / Claude / DeepSeek) 的高质量生产级 Prompt。"""
    key = site_key or "custom_site"
    name = site_name or "自定义影视源"

    html_section = f"""### 目标页面 HTML 片段参考（从真实源站提取）：
```html
{html_preview[:3000]}
```""" if html_preview else ""

    api_section = f"""### 目标接口/JSON 样例参考：
```json
{api_preview[:2500]}
```""" if api_preview else ""

    note_section = f"""### 特殊难点与逆向重点（加密/混淆/防盗链）：
{difficulty_note}""" if difficulty_note else ""

    cats_lines = []
    if categories_tree:
        for idx, cat in enumerate(categories_tree, 1):
            if not cat.get("selected", True):
                continue
            cat_name = cat.get("type_name") or cat.get("name") or "未命名分类"
            cat_tid = cat.get("type_id") or cat.get("tid") or str(idx)
            subs = cat.get("subcategories") or []
            subs_str = ", ".join(
                f"{s.get('type_name') or s.get('name')}(tid='{s.get('type_id') or s.get('tid')}')"
                for s in subs
                if s.get("selected", True)
            )
            cats_lines.append(f"{idx}. 一级分类【{cat_name}】(tid: '{cat_tid}'):\n   - 二级分类选项: {subs_str or '全部'}")

    cats_section = f"""### 用户明确指定的分类结构（必须在代码中严格实现，不可随意变动）：
你编写的采集器中的 `home()` 和 `category(tid, page)` 必须严格实现以下一级分类与二级子分类映射，确保每个分类点进去都能正确翻页抓取：
{chr(10).join(cats_lines)}
""" if cats_lines else ""

    fields_lines = []
    if detail_fields:
        for f in detail_fields:
            if f.get("selected", True):
                f_key = f.get("field_key") or f.get("field") or ""
                f_label = f.get("field_label") or f.get("label") or f_key
                f_sample = f.get("detected_sample") or f.get("sample") or ""
                status = f"（已探测到样本：{f_sample}）" if (f.get("found") or f_sample) else "（源站可能无此数据，拿不到勿编造）"
                fields_lines.append(f"- `{f_key}` ({f_label}): 必须采集 = {f.get('required', False)} {status}")

    fields_section = f"""### 用户明确指定的详情页信息采集清单（detail 方法提取标准）：
在 `detail(self, id)` 返回的字典中，必须根据源站实际提取以下已确认字段：
{chr(10).join(fields_lines)}
- **字段提取原则**：源站未提供的字段（如某些站无演员/导演/评分）切勿编造虚假数据，留空或不返回该键即可。
- **播放线路 (lines) 特别约定**：
  * 若用户未指定多线路选择器，或源站本身只有单一播放源/未提供线路切换选项卡，**切勿编造多条线路**，直接将提取出的所有剧集挂载到单个默认线路中返回：
    `"lines": [{{"id": "1", "name": "默认线路", "episodes": [...]}}]`；
  * 仅当源站页面有明显的线路切换 Tab 栏（如“蓝光专线”、“极速播放”、“量子专线”）时，才遍历提取多线路。
""" if fields_lines else ""

    prompt = f"""你是一名精通 Python 网络逆向与高并发爬虫架构的专家。请为我们的影视聚合流媒体系统编写一个针对目标源站【{name}】（目标主页：{target_url}）的单文件采集器脚本（适配器）。

{cats_section}
{fields_section}
{note_section}
{html_section}
{api_section}

### 一、系统核心硬约束（极其严格，不可违背）：
1. **零外部第三方重依赖**：
   - 严禁 `import requests`, `scrapy`, `selenium`, `playwright`, `bs4`, `parsel` 等外部库。
   - 只允许导入我们定制的轻量高性能工具箱 `from crawler_kit import Client, CrawlerError, clean, cli, log, parse` 以及 Python 标准库（`json`, `re`, `time`, `urllib`, `hashlib`, `base64`, `math` 等）；若遇到封面图片或媒体解密需求（如 AES-128-CBC/DES/ECB），明确允许导入标准 `cryptography` 库（如 `from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes`）。
2. **受限环境与 AST 安全审计**：
   - 代码将在沙盒进程中被 AST 语法树审计。严禁导入 `subprocess`, `ctypes`, `socket`, `pty`, `multiprocessing`, `shutil`, `importlib`，严禁使用 `eval()`, `exec()`, `os.system()`。
3. **统一输出信封与正常退出码**：
   - stdout **只允许输出一行合法的 JSON 信封**，格式为 `{{ "ok": true, "data": {{...}}, "error": null }}`。
   - 调试、跟踪日志必须通过 `log.info(...)` / `log.debug(...)` 输出（走 stderr，不污染 stdout）。
   - 进程即使在抓取或解析失败时，**正常退出码也必须是 0**，并以 JSON 报错信封返回：`{{ "ok": false, "data": null, "error": {{ "code": "PARSE_ERROR", "message": "错误原因" }} }}`。业务异常请直接 `raise CrawlerError("PARSE_ERROR", "原因")`。

### 二、采集器类结构与协议契约（必须严格对齐）：
脚本必须定义一个类，并在末尾调用 `cli.main(SiteClass())`。类必须包含以下成员：

```python
#: 单站专属代理配置（若留空则跟随全局环境变量或直连；支持填入 http://127.0.0.1:10809 或通过环境变量覆盖）
import os
SITE_PROXY = os.environ.get("PROXY_{key.upper()}", "").strip()

class {name.title().replace(' ', '')}Crawler:
    key = "{key}"
    name = "{name}"
    version = "1.0.0"       # 语义化版本号，后台覆盖部署时支持自动 patch 递增
    base_url = "{target_url}"
    mode = "direct"          # 播放模式：direct（播放器直连源站CDN）或 proxy（需后端中继代理）
    capabilities = ("meta", "home", "category", "detail", "play")

    def __init__(self, client=None):
        # 使用内置高性能 Client（支持自动重试、连接池、限速与单站独立代理）
        self.http = client or Client(
            base_url="{target_url}",
            timeout=15.0,
            retries=1,
            headers={{
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "{target_url}/",
            }},
            proxy=getattr(self, "proxy", None) or SITE_PROXY or None,
            min_interval=0.3,
        )
```

### 三、必须实现的标准动作方法（契约格式要求）：

1. **`meta(self)` -> dict**：
   返回站点基础元数据：
   `{{ "key": "{key}", "name": "{name}", "version": self.version, "base_url": self.base_url, "mode": self.mode, "capabilities": self.capabilities }}`

2. **`home(self)` -> dict**：
   返回首页大厅分类树与推荐片单：
   ```json
   {{
     "categories": [
       {{
         "tid": "10",
         "name": "电影",
         "subcategories": [
           {{ "tid": "10", "name": "全部电影" }},
           {{ "tid": "1001", "name": "动作片" }},
           {{ "tid": "1002", "name": "喜剧片" }}
         ]
       }}
     ],
     "recommend": [
       {{
         "vod_id": "12345",
         "vod_name": "影片标题",
         "vod_pic": "https://.../poster.jpg",
         "vod_remarks": "高清1080P/全24集",
         "vod_type": "动作",
         "vod_year": 2026
       }}
     ]
   }}
   ```
   *注意：分类必须返回树形 `categories[i].subcategories` 结构，方便前台二级联动筛选。*

3. **`category(self, tid, page=1)` -> dict**：
   返回指定分类下的分页影片列表：
   ```json
   {{
     "videos": [
       {{ "vod_id": "...", "vod_name": "...", "vod_pic": "...", "vod_remarks": "..." }}
     ],
     "page": int(page),
     "has_more": bool (根据是否有下一页计算)
   }}
   ```

4. **`detail(self, id)` -> dict**：
   返回影片完整详情、线路列表与各集剧集信息：
   ```json
   {{
     "video": {{
       "vod_id": "12345",
       "vod_name": "影片名称",
       "vod_pic": "https://.../poster.jpg",
       "vod_remarks": "更新至第12集",
       "vod_actor": "主演名单",
       "vod_director": "导演",
       "vod_area": "中国大陆",
       "vod_year": 2026,
       "vod_score": "9.2",
       "vod_hits": 18200,
       "vod_tag": "剧情,悬疑"
     }},
     "desc": "剧情简介简介...",
     "lines": [
       {{
         "id": "1",
         "name": "默认线路",
         "episodes": [
           {{ "ep_index": 1, "ep_name": "第01集", "play_id": "12345|line1|1" }},
           {{ "ep_index": 2, "ep_name": "第02集", "play_id": "12345|line1|2" }}
         ]
       }}
     ]
   }}
   ```

5. **`play(self, id=None, ep=1, play_id=None, line=1)` -> dict**：
   返回真实可播放的视频流地址（支持通过 `play_id` 定位符或 `(id, line, ep)` 提取）：
   ```json
   {{
     "url": "https://.../index.m3u8",
     "format": "m3u8",
     "headers": {{ "Referer": "{target_url}/" }}
   }}
   ```

6. **【重点扩展：封面/海报图片解密专项】`decode_image(content: bytes) -> tuple[bytes, str] | None`**：
   若该源站对封面/海报图片进行了前端加密（如通过 CryptoJS 执行 AES-128-CBC、异或或自定义字节混淆）：
   - 请深入分析目标站前端引用的 JS 脚本，逆向出其解密 Key、IV 和填充算法；
   - 在爬虫类上增加静态方法 `@staticmethod def decode_image(content: bytes) -> tuple[bytes, str] | None:`（也可作为模块级函数）；
   - 若传入的字节已是正常图片（头部为 JPEG `\xff\xd8\xff`、PNG `\x89PNG`、WEBP `RIFF`、GIF `GIF8`）必须直接返回 `None`；
   - 若为密文，解密成功后返回 `(decrypted_bytes, "image/jpeg" 或 "image/png")`，解密失败返回 `None`；
   - 务必使用标准库或 `cryptography` 实现解密；
   - 系统图片中继代理会自动感知该钩子并流式解密，爬虫抓取的 `vod_pic` 依然输出原图 URL 即可。

7. **【可选扩展】`mode = "proxy"` 与 `decode_media(content: bytes) -> bytes | None`**：
   若该源站对视频串流进行了伪装容器封装（如把 m3u8 清单与 TS 分片伪装包装进 PNG 图片容器，如 rou 等）或存在严格防盗链/白名单：
   - 在爬虫类上声明 `mode = "proxy"`（默认为 `"direct"`）；
   - 在爬虫类上增加静态方法 `@staticmethod def decode_media(content: bytes) -> bytes | None:`（也可作为模块级函数）；
   - 传入的字节若是伪装/加密数据，解封装后返回真实字节（m3u8 返回 `b"#EXTM3U..."` 文本字节，TS 分片返回以 `0x47` 同步字开头的 MPEG-TS 字节）；若无需解封装或非目标数据返回 `None`；
   - 系统流媒体中继代理（Stream Proxy）会自动把清单和分片递归改写并接管，自动调用该钩子解封装，吐出纯正的 m3u8 和 TS 流，前台播放器直接无缝播放。

### 四、影视海报与封面提取专项规范（关键防坑，重中之重）：
1. **绝不单纯提取 `node.attr('src')`**：现代影视站点与 CMS 绝大多数开启了图片懒加载，其 HTML 初始的 `src` 往往只是 1x1 像素的透明空白 base64 占位图（如 `data:image/gif...`）或 `loading.gif`。
2. **多重备选属性回退链**：在提取影片海报封面 `vod_pic` 时，必须按以下优先级顺序回退提取真实图床地址：
   ```python
   pic = (
       node.attr("data-src")
       or node.attr("data-original")
       or node.attr("data-lazy-src")
       or node.attr("data-echo")
       or node.attr("data-url")
       or node.attr("src")
       or ""
   )
   if pic.startswith("data:image"):
       pic = ""  # 滤除透明 base64 占位图
   pic = clean.absolute(pic, self.base_url)
   ```
3. **CSS 背景图兼容**：若目标站使用 `<div class="cover" style="background-image:url(...)">` 或 `data-bg` 渲染海报：
   ```python
   bg_url = node.attr("data-bg") or node.attr("data-background") or ""
   if not bg_url:
       style_text = node.attr("style") or ""
       bg_m = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style_text)
       if bg_m:
           bg_url = bg_m.group(1)
   if bg_url:
       pic = clean.absolute(bg_url, self.base_url)
   ```

### 五、内置 `crawler_kit` 核心工具链使用指南：
- **HTML 解析**：`root = parse.parse_html(html_text)`
  - 查找元素：`node = root.select_first("div.item")`，`items = root.select(".card-list .item")`
  - 获取文本与属性：`text = node.text`，`href = node.attr("href")`，`img = node.attr("data-src") or node.attr("data-original") or node.attr("src")`
- **数据清洗**：
  - `clean.strip_promo(text)`：自动滤除常见赌博广告、推广水印；
  - `clean.collapse(text)`：收缩多余空格换行；
  - `clean.absolute(url, self.base_url)`：把相对地址自动转为完整 HTTP URL；
  - `clean.to_int(val, default=1)`：安全转整数；
  - `clean.dedupe(list_items, key=lambda x: x["vod_id"])`：列表安全去重；
- **命令行主程序绑定**：
  ```python
  if __name__ == "__main__":
      cli.main({name.title().replace(' ', '')}Crawler())
  ```

{html_section}
{api_section}
{note_section}

### 输出要求（请严格遵守以下输出格式）：
1. **若逆向发现存在海报/封面加密**：
   请**必须在回答最上方单独输出一个标准 JSON 代码块**，标明逆向提取出的图片解密参数（供用户一键复制填入 Plove 管理后台，或系统部署时自动提取注册）：
   ```json
   {{
     "site_key": "{key}",
     "name": "{name}加密海报",
     "match_domains": ["目标图床域名，例如 pic.wirqed.cn"],
     "algorithm": "AES-128-CBC",
     "key": "十六进制或UTF-8密钥字符串",
     "iv": "偏移向量（CBC模式）",
     "is_hex": false
   }}
   ```
2. **单文件采集器脚本源码**：
   紧接着直接给出**完整、可运行、无省略、符合上述全部契约**的单文件 Python 脚本源码（用 ````python ... ```` 代码块包含），不要写虚构伪代码，确保选择器或正则切实符合上述样例！
"""
    return prompt
