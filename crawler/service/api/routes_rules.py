"""规则管理与在线调试 API。"""

from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

from ..core.errors import ErrorCode
from ..engine.extractor_html import extract_html_field, parse_html
from ..engine.extractor_json import extract_json_field
from ..engine.models import FieldExtractor
from ..engine.rule_manager import rule_manager

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


class TestFieldRequest(BaseModel):
    sample_content: str
    data_type: str = "html"  # html | json
    rule: FieldExtractor
    base_url: str = "https://example.com"


@router.get("", summary="获取所有站点库（包含 Python 脚本采集器与 JSON 规则）")
async def list_rules():
    sites = rule_manager.list_unified_sites()
    return {
        "ok": True,
        "data": sites,
        "error": None,
    }


@router.get("/script/{key}/code", summary="获取指定 Python 脚本源码")
async def get_script_code(key: str):
    code = rule_manager.get_script_code(key)
    return {
        "ok": True,
        "data": {
            "key": key,
            "code": code,
        },
        "error": None,
    }


@router.delete("/script/{key}", summary="从本地站点库删除指定 Python 采集脚本")
async def delete_script(key: str):
    ok = rule_manager.delete_script(key)
    return {
        "ok": ok,
        "data": {"deleted": key},
        "error": None,
    }


@router.get("/{key}")
async def get_rule(key: str):
    rule = rule_manager.get_rule(key)
    return {
        "ok": True,
        "data": rule.model_dump(),
        "error": None,
    }


@router.post("")
async def create_rule(rule_payload: dict[str, Any]):
    rule = rule_manager.save_rule(rule_payload)
    return {
        "ok": True,
        "data": rule.model_dump(),
        "error": None,
    }


@router.put("/{key}")
async def update_rule(key: str, rule_payload: dict[str, Any]):
    rule_payload["key"] = key
    rule = rule_manager.save_rule(rule_payload)
    return {
        "ok": True,
        "data": rule.model_dump(),
        "error": None,
    }


@router.delete("/{key}")
async def delete_rule(key: str):
    ok = rule_manager.delete_rule(key)
    return {
        "ok": ok,
        "data": {"deleted": key},
        "error": None,
    }


@router.post("/test")
async def test_extractor(req: TestFieldRequest):
    """在线测试单字段提取规则。输入 HTML 或 JSON 片段与规则，实时查看提取结果。"""
    try:
        extracted = ""
        if req.data_type == "json":
            import json
            parsed_json = json.loads(req.sample_content)
            extracted = extract_json_field(parsed_json, req.rule, req.base_url)
        else:
            root = parse_html(req.sample_content)
            extracted = extract_html_field(root, req.rule, req.base_url, full_html_text=req.sample_content)

        return {
            "ok": True,
            "data": {
                "extracted_value": extracted,
                "type": req.data_type,
            },
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": {
                "code": ErrorCode.PARSE_ERROR.value,
                "message": f"提取失败: {exc}",
            },
        }
