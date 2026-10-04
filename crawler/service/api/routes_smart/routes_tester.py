from __future__ import annotations

from fastapi import APIRouter

from ...engine.script_tester import ScriptTester
from .schemas import TestScriptRequest

router = APIRouter()


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
