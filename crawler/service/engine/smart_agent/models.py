from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class SmartExploreResult(BaseModel):
    base_url: str
    site_name: str
    suggested_key: str
    data_type: str
    categories: list[dict[str, Any]]
    recommend: list[dict[str, Any]]
    sample_detail: Optional[dict[str, Any]] = None
    sample_stream: Optional[dict[str, Any]] = None
    generated_rule: dict[str, Any]
    generated_python_code: str = ""
    steps_log: list[str]


class StructureInspectionResult(BaseModel):
    base_url: str
    site_name: str
    suggested_key: str
    categories_tree: list[dict[str, Any]]
    unassigned_tags: list[dict[str, str]]
    unassigned_tags_pool: list[dict[str, str]] = Field(default_factory=list)
    detail_fields: list[dict[str, Any]]
    sample_video: Optional[dict[str, Any]] = None
    html_preview: str = ""
    steps_log: list[str] = Field(default_factory=list)
