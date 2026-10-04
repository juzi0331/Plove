from __future__ import annotations

import urllib.parse
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from ...core.cleaner import collapse_whitespace, safe_resolve_url
from ...core.http_client import HttpClient
from ...engine.extractor_html import parse_html
from .visual_proxy_assets import build_injected_visual_proxy_html

router = APIRouter()


@router.get("/visual-proxy", summary="实时网页可视化交互代理与点选脚本中继")
async def visual_proxy(
    url: str = Query(..., description="目标站点网页 URL"),
    mode: str = Query("pick", description="拾取器初始模式: pick 或 browse"),
):
    """为指定网页提供同源代理中继，并动态注入可视化拾取器交互脚本。"""
    clean_url = url.strip()
    if not clean_url:
        return HTMLResponse("<div style='padding:2rem;color:#ef4444'>请输入有效的目标网址</div>", status_code=400)

    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"

    parsed = urllib.parse.urlparse(clean_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    try:
        async with HttpClient(base_url=base_url) as client:
            resp = await client.request("GET", clean_url)
            html = resp.text
            final_url = clean_url

            # 若页面只有极少数引导链接（如未成年门禁或过渡页），自动跟随进入主入口
            try:
                root = parse_html(html)
                if len(root.select("a")) <= 6:
                    for a in root.select("a"):
                        h = (a.attr("href") or "").strip()
                        t = collapse_whitespace(a.text)
                        if not h or h == "#" or h.startswith("javascript:"):
                            continue
                        if any(w in t for w in ["进入", "進入", "18", "滿", "满", "成年", "agree", "enter", "continue", "首页", "首頁"]) or h in ("/home", "/index.html", "/main"):
                            if not h.startswith("http") or any(dom in h for dom in (base_url, parsed.netloc)):
                                next_url = safe_resolve_url(base_url, h)
                                next_resp = await client.request("GET", next_url)
                                if next_resp.status_code == 200 and len(next_resp.text) > len(html):
                                    html = next_resp.text
                                    final_url = next_url
                                break
            except Exception:
                pass

            final_html = build_injected_visual_proxy_html(final_url, html, mode=mode)
            headers = {
                "X-Frame-Options": "ALLOWALL",
                "Content-Security-Policy": "frame-ancestors *;",
            }
            return HTMLResponse(content=final_html, headers=headers)
    except Exception as exc:
        err_html = f"""
        <div style="font-family:system-ui,sans-serif;padding:3rem;text-align:center;color:#334155;background:#f8fafc;min-height:100vh">
          <h2 style="font-size:1.4rem;font-weight:700;color:#ef4444;margin-bottom:1rem">网页代理中继加载失败</h2>
          <p style="font-size:0.95rem;color:#64748b;margin-bottom:1.5rem">无法连接并拉取目标页面: <code>{clean_url}</code></p>
          <div style="background:#fff;border:1px solid #e2e8f0;padding:1rem;border-radius:6px;font-family:monospace;font-size:0.85rem;color:#b91c1c;max-width:600px;margin:0 auto;text-align:left">
            {exc}
          </div>
          <p style="font-size:0.85rem;color:#94a3b8;margin-top:1.5rem">若该站点需要国外节点，请确保右上方已启用本地代理配置。</p>
        </div>
        """
        return HTMLResponse(content=err_html, status_code=200)
