from __future__ import annotations

import httpx
from fastapi import APIRouter

from ...core.errors import ErrorCode
from ...engine.rule_manager import rule_manager
from .schemas import DeployToBackendRequest, SaveRuleRequest, SaveScriptToLibraryRequest

router = APIRouter()


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
