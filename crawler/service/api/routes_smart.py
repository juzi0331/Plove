"""智能 URL 一键抓取、AI 提示词生成、脚本测试与规则固化 API。

全部接口配备清晰中文说明与参数简介。
"""

from typing import Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.errors import CrawlerServiceError, ErrorCode
from ..engine.prompt_generator import build_ai_crawler_prompt
from ..engine.rule_manager import rule_manager
from ..engine.script_tester import ScriptTester
from ..engine.smart_agent import SmartAgent, SmartExploreResult

router = APIRouter(prefix="/api/v1/smart", tags=["智能采集与脚本工坊"])


class SmartExploreRequest(BaseModel):
    url: str = Field(..., description="目标站点主页 URL，例如 https://example.com")


class GeneratePromptRequest(BaseModel):
    url: str = Field(..., description="目标站点主页 URL")
    site_name: Optional[str] = Field("", description="站点展示名称")
    site_key: Optional[str] = Field("", description="站点英文标识")
    html_preview: Optional[str] = Field("", description="目标页截取的 HTML 片段")
    difficulty_note: Optional[str] = Field("", description="难点说明（如 Cloudflare 闸门、JS 混淆签名等）")


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


@router.post("/generate-prompt", summary="生成交付给外部 AI 的编写提示词 (Prompt)")
async def generate_prompt(req: GeneratePromptRequest):
    """针对高难度站点（加密、混淆、特殊防爬），将侦察上下文打包成带有严格项目契约的专业 Prompt，供用户复制并发送给 ChatGPT / Claude / DeepSeek。"""
    prompt = build_ai_crawler_prompt(
        target_url=req.url,
        site_name=req.site_name or "",
        site_key=req.site_key or "",
        html_preview=req.html_preview or "",
        difficulty_note=req.difficulty_note or "",
    )
    return {
        "ok": True,
        "data": {
            "prompt": prompt,
            "char_count": len(prompt),
        },
        "error": None,
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
