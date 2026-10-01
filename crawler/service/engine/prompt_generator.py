"""专门用于向外部 AI（如 ChatGPT、Claude、DeepSeek）提问的针对性 Prompt 生成器。

当遇到高难度站点（加密、混淆、特殊反爬、非标准接口）时，
将目标站侦察到的上下文与 Plove 严格的后端爬虫契约打包为专业提示词，
让外部 AI 能够直接输出 100% 符合本项目标准的单文件 Python 脚本。
"""

from __future__ import annotations

import json
from typing import Any, Optional


def build_ai_crawler_prompt(
    target_url: str,
    site_name: str = "",
    site_key: str = "",
    html_preview: str = "",
    api_preview: str = "",
    difficulty_note: str = "",
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

    prompt = f"""你是一名精通 Python 网络逆向与高并发爬虫架构的专家。请为我们的影视聚合流媒体系统编写一个针对目标源站【{name}】（目标主页：{target_url}）的单文件采集器脚本（适配器）。

### 一、系统核心硬约束（极其严格，不可违背）：
1. **零外部第三方重依赖**：
   - 严禁 `import requests`, `scrapy`, `selenium`, `playwright`, `bs4`, `parsel` 等外部库。
   - 只允许导入我们定制的轻量高性能工具箱 `from crawler_kit import Client, CrawlerError, clean, cli, log, parse` 以及 Python 标准库（`json`, `re`, `time`, `urllib`, `hashlib`, `base64`, `math` 等）。
2. **受限环境与 AST 安全审计**：
   - 代码将在沙盒进程中被 AST 语法树审计。严禁导入 `subprocess`, `ctypes`, `socket`, `pty`, `multiprocessing`, `shutil`, `importlib`，严禁使用 `eval()`, `exec()`, `os.system()`。
3. **统一输出信封与正常退出码**：
   - stdout **只允许输出一行合法的 JSON 信封**，格式为 `{{ "ok": true, "data": {{...}}, "error": null }}`。
   - 调试、跟踪日志必须通过 `log.info(...)` / `log.debug(...)` 输出（走 stderr，不污染 stdout）。
   - 进程即使在抓取或解析失败时，**正常退出码也必须是 0**，并以 JSON 报错信封返回：`{{ "ok": false, "data": null, "error": {{ "code": "PARSE_ERROR", "message": "错误原因" }} }}`。业务异常请直接 `raise CrawlerError("PARSE_ERROR", "原因")`。

### 二、采集器类结构与协议契约（必须严格对齐）：
脚本必须定义一个类，并在末尾调用 `cli.main(SiteClass())`。类必须包含以下成员：

```python
class {name.title().replace(' ', '')}Crawler:
    key = "{key}"
    name = "{name}"
    version = "1.0.0"       # 语义化版本号，后台覆盖部署时支持自动 patch 递增
    base_url = "{target_url}"
    mode = "direct"          # 播放模式：direct（播放器直连源站CDN）或 proxy（需后端中继代理）
    capabilities = ("meta", "home", "category", "detail", "play")

    def __init__(self, client=None):
        # 使用内置高性能 Client（支持自动重试、连接池与限速）
        self.http = client or Client(
            base_url="{target_url}",
            timeout=15.0,
            retries=1,
            headers={{
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "{target_url}/",
            }},
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
       "vod_year": 2026
     }},
     "desc": "剧情简介简介...",
     "lines": [
       {{
         "id": "1",
         "name": "蓝光极速线",
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

### 四、内置 `crawler_kit` 核心工具链使用指南：
- **HTML 解析**：`root = parse.parse_html(html_text)`
  - 查找元素：`node = root.select_first("div.item")`，`items = root.select(".card-list .item")`
  - 获取文本与属性：`text = node.text`，`href = node.attr("href")`，`img = node.attr("data-src") or node.attr("src")`
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

### 输出要求：
请直接给出**完整、可运行、无省略、符合上述全部契约**的单文件 Python 脚本源码（用 markdown ````python ... ```` 代码块包含），不要写虚构伪代码，确保选择器或正则切实符合上述样例！
"""
    return prompt
