from __future__ import annotations

from fastapi import APIRouter

from ...engine.code_generator import generate_crawler_python_code
from ...engine.prompt_generator import build_ai_crawler_prompt
from .schemas import GenerateCodeRequest, GeneratePromptRequest

router = APIRouter()


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
