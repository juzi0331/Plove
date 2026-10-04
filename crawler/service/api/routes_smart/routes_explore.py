from __future__ import annotations

from fastapi import APIRouter

from ...core.errors import ErrorCode
from ...engine.smart_agent import SmartAgent
from .schemas import InspectStructureRequest, SmartExploreRequest

router = APIRouter()


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
