"""智能 URL 一键抓取、AI 提示词生成、脚本测试与规则固化 API。

全部接口配备清晰中文说明与参数简介。
"""

import re
import urllib.parse
from typing import Any, Optional
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..core.cleaner import collapse_whitespace, safe_resolve_url
from ..core.errors import ErrorCode
from ..core.http_client import HttpClient
from ..engine.code_generator import generate_crawler_python_code
from ..engine.extractor_html import parse_html
from ..engine.prompt_generator import build_ai_crawler_prompt
from ..engine.rule_manager import rule_manager
from ..engine.script_tester import ScriptTester
from ..engine.smart_agent import SmartAgent

router = APIRouter(prefix="/api/v1/smart", tags=["智能采集与脚本工坊"])


class SmartExploreRequest(BaseModel):
    url: str = Field(..., description="目标站点主页 URL，例如 https://example.com")


class InspectStructureRequest(BaseModel):
    url: str = Field(..., description="目标站点主页 URL，用于可视化探测分类树与详情字段")


class GeneratePromptRequest(BaseModel):
    url: str = Field(..., description="目标站点主页 URL")
    site_name: Optional[str] = Field("", description="站点展示名称")
    site_key: Optional[str] = Field("", description="站点英文标识")
    html_preview: Optional[str] = Field("", description="目标页截取的 HTML 片段")
    difficulty_note: Optional[str] = Field("", description="难点说明（如 Cloudflare 闸门、JS 混淆签名等）")
    categories_tree: Optional[list[dict[str, Any]]] = Field(None, description="用户确认的一级分类与二级子分类树")
    detail_fields: Optional[list[dict[str, Any]]] = Field(None, description="用户确认的详情页采集字段列表")


class GenerateCodeRequest(BaseModel):
    key: Optional[str] = Field(None, description="站点英文 key")
    name: Optional[str] = Field(None, description="站点中文名称")
    site_key: Optional[str] = Field(None, description="站点英文标识")
    site_name: Optional[str] = Field(None, description="站点中文名称")
    url: str = Field(..., description="目标站点主页 URL")
    mode: Optional[str] = Field("direct", description="播放代理模式 direct 或 proxy")
    categories_tree: Optional[list[dict[str, Any]]] = Field(None, description="用户确认的分类树")
    detail_fields: Optional[list[dict[str, Any]]] = Field(None, description="用户确认的字段列表")


class TestScriptRequest(BaseModel):
    code: str = Field(..., description="外部 AI 编写或导入的完整 Python 采集脚本代码")
    custom_key: Optional[str] = Field(None, description="可选的站点 key")



class SaveRuleRequest(BaseModel):
    rule: dict[str, Any] = Field(..., description="SiteRule 规范字典")


class DeployToBackendRequest(BaseModel):
    backend_url: str = Field("http://127.0.0.1:8000", description="Plove 后端服务根地址")
    admin_token: str = Field("admin", description="管理员后台令牌 (X-Admin-Token)")
    key: str = Field(..., description="站点英文 key")
    code: str = Field(..., description="Python 采集器脚本代码")
    overwrite: bool = Field(True, description="若站点已存在是否允许覆盖")


@router.post("/explore", summary="智能自适应探索：输入主页 URL 搞定一切")
async def explore_url(req: SmartExploreRequest):
    """自动连接源站、探测编码、破解反爬闸门、提取分类、聚类海报、穿透详情并自动生成合规的 Python 采集脚本。"""
    if not req.url or not req.url.strip():
        return {
            "ok": False,
            "data": None,
            "error": {"code": ErrorCode.BAD_REQUEST.value, "message": "请输入有效的主页 URL"},
        }

    try:
        agent = SmartAgent(req.url)
        res = await agent.explore()
        return {
            "ok": True,
            "data": res.model_dump(),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": {
                "code": ErrorCode.PARSE_ERROR.value,
                "message": f"智能探索失败: {exc}",
            },
        }


@router.post("/inspect-structure", summary="可视化结构勘探：发现一级/二级分类与详情页字段")
async def inspect_structure(req: InspectStructureRequest):
    """连接目标源站，深度探测并归类一级分类、二级子标签池，以及详情页全部可用字段，供前端可视化勾选与调整。"""
    if not req.url or not req.url.strip():
        return {
            "ok": False,
            "data": None,
            "error": {"code": ErrorCode.BAD_REQUEST.value, "message": "请输入有效的主页 URL"},
        }

    try:
        agent = SmartAgent(req.url)
        res = await agent.inspect_structure()
        return {
            "ok": True,
            "data": res.model_dump(),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": {
                "code": ErrorCode.PARSE_ERROR.value,
                "message": f"结构勘探失败: {exc}",
            },
        }


@router.post("/generate-prompt", summary="根据用户确认的分类与字段，生成专属 AI 编写提示词 (Prompt)")
async def generate_prompt(req: GeneratePromptRequest):
    """将用户在可视化面板中已确认的一级标签、二级标签、详情页必须采集的字段，与目标站实测 HTML、反爬难点融合打包成零歧义的顶级 Prompt。"""
    prompt = build_ai_crawler_prompt(
        target_url=req.url,
        site_name=req.site_name or "",
        site_key=req.site_key or "",
        html_preview=req.html_preview or "",
        difficulty_note=req.difficulty_note or "",
        categories_tree=req.categories_tree,
        detail_fields=req.detail_fields,
    )
    return {
        "ok": True,
        "data": {
            "prompt": prompt,
            "char_count": len(prompt),
        },
        "error": None,
    }


@router.post("/generate-code", summary="根据用户确认的分类与字段配置，直接自动生成 Python 采集器脚本")
async def generate_code(req: GenerateCodeRequest):
    """根据可视化界面确认的一级/二级分类映射与字段配置，直接合成标准的 sites/<key>.py 单文件采集器。"""
    effective_key = req.key or req.site_key or "custom_site"
    effective_name = req.name or req.site_name or "自定义影视"
    try:
        code = generate_crawler_python_code(
            key=effective_key,
            name=effective_name,
            base_url=req.url,
            mode=req.mode or "direct",
            categories=req.categories_tree,
        )
        return {
            "ok": True,
            "data": {
                "key": effective_key,
                "name": effective_name,
                "python_code": code,
                "code": code,
                "lines_count": len(code.splitlines()),
            },
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": {"code": "GENERATE_FAILED", "message": f"代码生成失败: {exc}"},
        }


@router.post("/test-script", summary="外部 AI 脚本导入与全链路自动化测试")
async def test_imported_script(req: TestScriptRequest):
    """将外部 AI 生成的 Python 脚本在隔离环境中进行全面体检：1. AST 安全审计 -> 2. meta 冒烟 -> 3. home 抓取 -> 4. detail 穿透 -> 5. play 嗅探。测试全绿后才允许部署到后端。"""
    if not req.code or len(req.code.strip()) < 20:
        return {
            "ok": False,
            "data": None,
            "error": {"code": "INVALID_CODE", "message": "传入的代码内容过短或为空"},
        }

    tester = ScriptTester(code=req.code, custom_key=req.custom_key)
    report = tester.run_full_suite()
    return {
        "ok": True,
        "data": report.model_dump(),
        "error": None,
    }


@router.post("/save-rule", summary="一键固化并保存站点规则到本地规则库")
async def save_smart_rule(req: SaveRuleRequest):
    try:
        rule = rule_manager.save_rule(req.rule)
        return {
            "ok": True,
            "data": {
                "key": rule.key,
                "name": rule.name,
                "message": f"站点规则 {rule.name} ({rule.key}) 已成功落盘生效！",
            },
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": {
                "code": ErrorCode.RULE_SYNTAX_ERROR.value,
                "message": f"固化规则失败: {exc}",
            },
        }


@router.post("/deploy-to-backend", summary="将测试通过的采集器脚本上传并热部署到 Plove 后端")
async def deploy_to_backend(req: DeployToBackendRequest):
    """通过 HTTP API 协同将测试通过的 Python 脚本一键上传落盘到 Plove 后端的 crawler/sites/<key>.py 并热重载激活。"""
    import httpx

    base = req.backend_url.rstrip("/")
    headers = {
        "X-Admin-Token": req.admin_token,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. 静态安全审计与冒烟协议测试
        try:
            val_resp = await client.post(
                f"{base}/api/v1/admin/crawlers/validate",
                headers=headers,
                json={"code": req.code, "key": req.key},
            )
            val_data = val_resp.json()
            if not val_data.get("ok"):
                err = val_data.get("error", {})
                return {
                    "ok": False,
                    "data": None,
                    "error": {
                        "code": "VALIDATE_FAILED",
                        "message": f"后端校验失败: {err.get('message', '未知错误')}",
                    },
                }
            val_res = val_data.get("data", {})
            if not val_res.get("valid"):
                return {
                    "ok": False,
                    "data": None,
                    "error": {
                        "code": "VALIDATE_FAILED",
                        "message": f"代码未通过安全审查或冒烟测试: {val_res.get('error')}",
                    },
                }
        except Exception as exc:
            return {
                "ok": False,
                "data": None,
                "error": {"code": "CONNECT_ERROR", "message": f"无法连接后端校验接口: {exc}"},
            }

        # 2. 正式上传热落盘部署
        try:
            up_resp = await client.post(
                f"{base}/api/v1/admin/crawlers/upload",
                headers=headers,
                json={"key": req.key, "code": req.code, "overwrite": req.overwrite},
            )
            up_data = up_resp.json()
            if not up_data.get("ok"):
                err = up_data.get("error", {})
                return {
                    "ok": False,
                    "data": None,
                    "error": {
                        "code": "UPLOAD_FAILED",
                        "message": f"后端落盘部署失败: {err.get('message', '未知错误')}",
                    },
                }

            return {
                "ok": True,
                "data": {
                    "message": f"成功上传并热部署到后端！站点 {req.key} 已在线就绪！",
                    "details": up_data.get("data"),
                },
                "error": None,
            }
        except Exception as exc:
            return {
                "ok": False,
                "data": None,
                "error": {"code": "CONNECT_ERROR", "message": f"无法连接后端上传接口: {exc}"},
            }


class SaveScriptToLibraryRequest(BaseModel):
    key: str = Field(..., description="站点英文 key")
    code: str = Field(..., description="Python 采集器脚本源码")


@router.post("/save-script-to-library", summary="将测试通过的 Python 脚本收录至本地站点与规则库")
async def save_script_to_library(req: SaveScriptToLibraryRequest):
    """将外部导入并通过体检的 Python 采集脚本存入本微服务的站点库中，便于长期维护与测试。"""
    try:
        res = rule_manager.save_script(req.key, req.code)
        return {
            "ok": True,
            "data": {
                "message": f"采集器脚本 {req.key}.py 已成功收录并保存至本地站点库！",
                "details": res,
            },
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": {
                "code": ErrorCode.RULE_SYNTAX_ERROR.value,
                "message": f"收录失败: {exc}",
            },
        }


def _build_injected_visual_proxy_html(target_url: str, html_content: str, mode: str = "pick") -> str:
    """为目标页面注入 <base> 与可视化元素点选拾取器脚本。"""
    # 移除原站 CSP 与 X-Frame-Options 相关的 meta 标签，防止其限制在 iframe 中运行或阻断通信
    cleaned_html = re.sub(
        r'<meta[^>]+http-equiv=["\']?(?:Content-Security-Policy|X-Frame-Options)["\']?[^>]*>',
        "",
        html_content,
        flags=re.IGNORECASE,
    )
    # 移除原站可能的 frame-busting 恶意顶层跳转代码
    cleaned_html = re.sub(
        r'(?:window\.)?top\.location\s*=\s*(?:window\.)?self\.location',
        "/* neutralized frame-busting */",
        cleaned_html,
        flags=re.IGNORECASE,
    )

    base_tag = f'<base href="{target_url}"/>'
    initial_mode = "browse" if mode == "browse" else "pick"

    injected_assets = f"""
    {base_tag}
    <style id="__plove_visual_picker_styles">
      #__plove_inspect_overlay {{
        position: fixed !important;
        pointer-events: none !important;
        z-index: 2147483647 !important;
        border: 2px solid #2563eb !important;
        background: rgba(37, 99, 235, 0.15) !important;
        box-shadow: 0 0 10px rgba(37, 99, 235, 0.4) !important;
        transition: all 0.05s ease-out !important;
        border-radius: 4px !important;
        box-sizing: border-box !important;
        display: none;
      }}
      #__plove_inspect_badge {{
        position: fixed !important;
        pointer-events: none !important;
        z-index: 2147483647 !important;
        background: #0f172a !important;
        color: #38bdf8 !important;
        border: 1px solid #334155 !important;
        font-size: 11px !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        padding: 2px 7px !important;
        border-radius: 4px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.35) !important;
        white-space: nowrap !important;
        max-width: 360px !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: none;
      }}
    </style>
    <script id="__plove_visual_picker_script">
    (function() {{
      if (window.__plove_picker_installed) return;
      window.__plove_picker_installed = true;

      var currentMode = "{initial_mode}";
      var isPickingMode = (currentMode === "pick");

      var overlay = document.createElement('div');
      overlay.id = '__plove_inspect_overlay';

      var badge = document.createElement('div');
      badge.id = '__plove_inspect_badge';

      function ensureMount() {{
        if (!document.body) return;
        if (!document.getElementById('__plove_inspect_overlay')) {{
          document.body.appendChild(overlay);
        }}
        if (!document.getElementById('__plove_inspect_badge')) {{
          document.body.appendChild(badge);
        }}
      }}

      function notifyPageReady() {{
        ensureMount();
        try {{
          window.parent.postMessage({{
            type: 'PLOVE_PAGE_READY',
            url: '{target_url}',
            mode: currentMode,
            title: document.title || ''
          }}, '*');
        }} catch(e) {{}}
      }}

      if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', notifyPageReady);
      }} else {{
        notifyPageReady();
      }}

      function getCssSelector(el) {{
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return '#' + el.id;
        var parts = [];
        var curr = el;
        while (curr && curr.nodeType === 1 && parts.length < 3) {{
          var tag = curr.tagName.toLowerCase();
          var classPart = '';
          if (curr.className && typeof curr.className === 'string') {{
            var cls = curr.className.trim().split(/\\s+/).filter(function(c) {{
              return c && !c.startsWith('__plove') && !c.includes(':');
            }}).slice(0, 2);
            if (cls.length > 0) {{
              classPart = '.' + cls.join('.');
            }}
          }}
          parts.unshift(tag + classPart);
          curr = curr.parentElement;
        }}
        return parts.join(' > ');
      }}

      function findSimilarElements(el) {{
        var results = [];
        if (!el || !el.parentElement) return results;

        var tag = el.tagName.toLowerCase();
        var parent = el.parentElement;
        var candidateElements = [];

        // 策略 A: 同父级容器下的相同标签兄弟节点 (例如 div.tags > a 或 ul > li)
        var parentChildren = Array.from(parent.children).filter(function(child) {{
          return !child.id || !child.id.startsWith('__plove');
        }});

        if (parentChildren.length > 1) {{
          var sameTagChildren = parentChildren.filter(function(c) {{
            return c.tagName.toLowerCase() === tag;
          }});
          if (sameTagChildren.length > 1) {{
            candidateElements = sameTagChildren;
          }}
        }}

        // 策略 B: 两级嵌套列表结构 (例如 ul > li > a，点击的是 a)
        if (candidateElements.length <= 1 && parent.parentElement) {{
          var grandParent = parent.parentElement;
          var grandChildren = Array.from(grandParent.children).filter(function(child) {{
            return !child.id || !child.id.startsWith('__plove');
          }});
          if (grandChildren.length > 1) {{
            var extracted = [];
            for (var i = 0; i < grandChildren.length; i++) {{
              var gc = grandChildren[i];
              var sub = gc.tagName.toLowerCase() === tag ? gc : gc.querySelector(tag);
              if (sub) {{
                extracted.push(sub);
              }}
            }}
            if (extracted.length > 1) {{
              candidateElements = extracted;
            }}
          }}
        }}

        // 策略 C: 相同 class 的同祖先兄弟项
        if (candidateElements.length <= 1 && el.className && typeof el.className === 'string') {{
          var firstCls = el.className.trim().split(/\\s+/).filter(function(c) {{
            return c && !c.startsWith('__plove') && !c.includes(':');
          }})[0];
          if (firstCls) {{
            var ancestor = el.closest('nav, ul, ol, .nav, .menu, .tags, .filter, .list, .module, .tab') || parent.parentElement || parent;
            if (ancestor) {{
              try {{
                var classMatches = Array.from(ancestor.querySelectorAll('.' + firstCls));
                if (classMatches.length > 1 && classMatches.length <= 60) {{
                  candidateElements = classMatches;
                }}
              }} catch (err) {{}}
            }}
          }}
        }}

        // 遍历提取候选元素的属性与文本
        var seenTexts = {{}};
        for (var j = 0; j < candidateElements.length; j++) {{
          var item = candidateElements[j];
          var targetItem = (tag === 'a' && item.tagName.toLowerCase() !== 'a') ? (item.querySelector('a') || item) : item;
          var txt = (targetItem.innerText || targetItem.textContent || '').trim().replace(/\\s+/g, ' ');
          if (!txt || txt.length > 40) continue;
          if (seenTexts[txt]) continue;
          seenTexts[txt] = true;

          var anchor = targetItem.tagName.toUpperCase() === 'A' ? targetItem : (targetItem.closest('a') || targetItem.querySelector('a'));
          var href = anchor ? (anchor.getAttribute('href') || '') : '';
          var fullHref = '';
          if (href && !href.startsWith('javascript:') && !href.startsWith('#')) {{
            try {{
              fullHref = new URL(href, document.baseURI).href;
            }} catch (err) {{
              fullHref = href;
            }}
          }}

          results.push({{
            text: txt,
            href: fullHref || href,
            selector: getCssSelector(targetItem),
            tagName: targetItem.tagName.toUpperCase()
          }});
        }}

        return results;
      }}

      function extractElementData(el) {{
        var rect = el.getBoundingClientRect();
        var tagName = el.tagName.toUpperCase();
        var text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
        var anchor = el.closest('a');
        var rawHref = (anchor ? anchor.getAttribute('href') : el.getAttribute('href')) || '';
        var fullHref = '';
        if (rawHref && !rawHref.startsWith('javascript:') && !rawHref.startsWith('#')) {{
          try {{
            fullHref = new URL(rawHref, document.baseURI).href;
          }} catch (err) {{
            fullHref = rawHref;
          }}
        }}
        var img = el.tagName.toUpperCase() === 'IMG' ? el : el.querySelector('img');
        var src = img ? (img.getAttribute('src') || img.getAttribute('data-original') || img.getAttribute('data-src') || '') : '';

        return {{
          tagName: tagName,
          text: text.slice(0, 160),
          href: fullHref || rawHref,
          src: src,
          selector: getCssSelector(el),
          rect: {{
            top: rect.top,
            left: rect.left,
            width: rect.width,
            height: rect.height
          }},
          siblings: findSimilarElements(el)
        }};
      }}

      document.addEventListener('mouseover', function(e) {{
        if (!isPickingMode) return;
        var target = e.target;
        if (!target || target === overlay || target === badge || (target.id && target.id.startsWith('__plove'))) return;
        ensureMount();

        var rect = target.getBoundingClientRect();
        overlay.style.top = rect.top + 'px';
        overlay.style.left = rect.left + 'px';
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
        overlay.style.display = 'block';

        var selector = getCssSelector(target);
        badge.innerText = selector;
        badge.style.top = Math.max(0, rect.top - 24) + 'px';
        badge.style.left = rect.left + 'px';
        badge.style.display = 'block';

        window.parent.postMessage({{
          type: 'PLOVE_ELEMENT_HOVERED',
          data: extractElementData(target)
        }}, '*');
      }}, true);

      document.addEventListener('mouseout', function(e) {{
        if (!isPickingMode) return;
        overlay.style.display = 'none';
        badge.style.display = 'none';
      }}, true);

      document.addEventListener('click', function(e) {{
        var target = e.target;
        if (!target || target === overlay || target === badge) return;

        var isCtrlClick = !!(e.ctrlKey || e.metaKey);
        var anchor = target.closest('a');

        // 穿透跳转机制: 任何模式下按住 Ctrl/Cmd 键点击链接，直接跳转进入新页面
        if (isCtrlClick && anchor && anchor.getAttribute('href')) {{
          var ctrlHref = anchor.getAttribute('href');
          if (ctrlHref && !ctrlHref.startsWith('#') && !ctrlHref.startsWith('javascript:')) {{
            e.preventDefault();
            e.stopPropagation();
            try {{
              var fullUrl = new URL(ctrlHref, document.baseURI).href;
              window.parent.postMessage({{
                type: 'PLOVE_NAVIGATE_PAGE',
                url: fullUrl,
                mode: currentMode
              }}, '*');
              window.location.href = '/api/v1/smart/visual-proxy?url=' + encodeURIComponent(fullUrl) + '&mode=' + encodeURIComponent(currentMode);
              return;
            }} catch (err) {{
              console.warn('URL 解析失败', err);
            }}
          }}
        }}

        if (isPickingMode) {{
          e.preventDefault();
          e.stopPropagation();
          var data = extractElementData(target);
          window.parent.postMessage({{
            type: 'PLOVE_ELEMENT_CLICKED',
            data: data
          }}, '*');
        }} else {{
          // 自由浏览模式下拦截站内 a 标签并重写走代理，同时保持当前 browse 模式不变
          if (anchor && anchor.getAttribute('href')) {{
            var rawHref = anchor.getAttribute('href');
            if (rawHref && !rawHref.startsWith('#') && !rawHref.startsWith('javascript:')) {{
              e.preventDefault();
              try {{
                var fullUrl = new URL(rawHref, document.baseURI).href;
                window.parent.postMessage({{
                  type: 'PLOVE_NAVIGATE_PAGE',
                  url: fullUrl,
                  mode: currentMode
                }}, '*');
                window.location.href = '/api/v1/smart/visual-proxy?url=' + encodeURIComponent(fullUrl) + '&mode=' + encodeURIComponent(currentMode);
              }} catch (err) {{
                console.warn('URL 解析失败', err);
              }}
            }}
          }}
        }}
      }}, true);

      window.addEventListener('message', function(evt) {{
        if (!evt.data) return;
        if (evt.data.type === 'PLOVE_SET_MODE') {{
          currentMode = evt.data.mode;
          isPickingMode = (currentMode === 'pick');
          if (!isPickingMode) {{
            overlay.style.display = 'none';
            badge.style.display = 'none';
          }}
        }}
      }});
    }})();
    </script>
    """

    # 尝试将 <base> 及脚本注入至 <head> 或最前端
    head_match = re.search(r"<head[^>]*>", cleaned_html, re.IGNORECASE)
    if head_match:
        pos = head_match.end()
        result = cleaned_html[:pos] + injected_assets + cleaned_html[pos:]
    else:
        result = injected_assets + cleaned_html

    return result


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

            final_html = _build_injected_visual_proxy_html(final_url, html, mode=mode)
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
