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
    """合成针对外部 AI 的高质量 Prompt。"""
    key = site_key or "custom_site"
    name = site_name or "自定义影视站"

    html_section = f"""### 目标页面 HTML 片段参考（截取）：
```html
{html_preview[:2500]}
```""" if html_preview else ""

    api_section = f"""### 目标接口/JSON 样例参考：
```json
{api_preview[:2000]}
```""" if api_preview else ""

    note_section = f"""### 特殊难点说明：
{difficulty_note}""" if difficulty_note else ""

    prompt = f"""你是一名精通 Python 网络爬虫与逆向工程的高级工程师。请为我们的影视聚合系统编写一个针对站点【{name}】（目标主页：{target_url}）的单文件爬虫脚本。

### 项目硬约束与架构规范（极其重要，不可违反）：
1. **零外部大依赖**：只允许 `import crawler_kit` 以及 Python 标准库（如 `urllib`, `re`, `json`, `hashlib`, `base64`, `time` 等）。**绝对禁止**导入 `requests`, `scrapy`, `selenium`, `playwright`, `parsel`, `bs4` 等外部库。
2. **安全合规硬红线**：代码将在受保护子进程中被 AST 审计。**严禁导入** `subprocess`, `ctypes`, `socket`, `pty`, `multiprocessing`, `shutil`, `importlib`，**严禁使用** `eval`, `exec`, `os.system`。
3. **输出信封与协议**：
   - 爬虫的 stdout **只允许输出一行合法 JSON**，任何日志、调试信息必须通过 `log.debug` / `log.info` 走 stderr。
   - 进程的**正常退出码永远是 0**，即使抓取失败也必须返回 `ok: false` 信封：
     `{{"ok": true, "data": {{...}}, "error": null}}` 或
     `{{"ok": false, "data": null, "error": {{"code": "PARSE_ERROR", "message": "错误原因"}}}}`
4. **必须实现的标准动作方法**：
   - `meta(self)`: 返回站点元数据 `{{ "key": "{key}", "name": "{name}", "version": "1.0.0", "base_url": "{target_url}", "mode": "direct", "capabilities": ["meta", "home", "category", "detail", "play"] }}`
   - `home(self)`: 返回首页分类与推荐影片 `{{ "categories": [{{"tid": "1", "name": "分类名"}}], "recommend": [VodItem] }}`
   - `category(self, tid, page=1)`: 返回指定分类的分页片单 `{{ "videos": [VodItem], "page": int(page), "has_more": bool }}`
   - `detail(self, id)`: 返回影片详情与选集 `{{ "video": VodItem, "desc": str, "episodes": [{{"ep_index": 1, "ep_name": "第1集", "play_id": str, "line": "1"}}], "lines": [...] }}`
   - `play(self, id=None, ep=1, play_id=None, line=None)`: 返回视频流 `{{ "url": "https://...m3u8", "format": "m3u8", "headers": {{...}} }}`
   - VodItem 的归一化字段：`{{"vod_id": str, "vod_name": str, "vod_pic": str, "vod_remarks": str}}`

5. **工具箱 `crawler_kit` 提供的方法**：
   - `Client(base_url, timeout, headers)`: 提供了类似 requests 的 `.get(url, params)` 方法，返回 `resp.text`, `resp.ok`, `resp.status`。
   - `parse.parse_html(html)`: 构建 DOM 树，支持 CSS 选择器 `.select("...")` 和 `.select_first("...")`，节点有 `.text` 与 `.attr("...")`。
   - `clean.clean_title(text)` / `clean.clean_text(text)` / `clean.safe_relative_path(base_url, path)`。
   - `cli.main(SiteClass())`: 命令行主入口绑定。

{html_section}
{api_section}
{note_section}

### 请输出：
请直接给出完整、可立即运行的 Python 单文件源代码（包含 `if __name__ == '__main__': cli.main(...)`），不要有任何省略或伪代码。
"""
    return prompt
