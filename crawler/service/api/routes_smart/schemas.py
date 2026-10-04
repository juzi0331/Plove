from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


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


class SaveScriptToLibraryRequest(BaseModel):
    key: str = Field(..., description="站点英文 key")
    code: str = Field(..., description="Python 采集器脚本源码")
