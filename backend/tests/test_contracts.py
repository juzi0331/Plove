"""契约测试。

契约是"三端唯一事实源"，所以这里管两件事：

1. 导出的 JSON 本身得是**合法的 JSON Schema**（前端 codegen 与爬虫侧校验都依赖这一点）；
2. 仓库里躺着的生成物必须**与模型一致**——过期就红，不许悄悄腐烂。
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from app.contracts import render, stale_contracts, write_contracts
from app.core.config import get_settings
from app.schemas import EXPORTS


@pytest.mark.parametrize("stem", sorted(EXPORTS))
def test_generated_schema_is_valid(stem):
    schema = json.loads(render(stem, EXPORTS[stem]))
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("stem", sorted(EXPORTS))
def test_generated_schema_has_identity(stem):
    schema = json.loads(render(stem, EXPORTS[stem]))
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["$id"].endswith(f"/{stem}.json")


def test_contracts_on_disk_are_not_stale():
    stale = stale_contracts(get_settings().schemas_dir)
    assert not stale, (
        "契约与模型不一致（或尚未导出），请运行 "
        f"python tools/export_contracts.py：{stale}"
    )


def test_write_then_check_is_clean(tmp_path):
    written = write_contracts(tmp_path)
    assert sorted(written) == sorted(f"{stem}.json" for stem in EXPORTS)
    assert stale_contracts(tmp_path) == []


def test_vod_item_requires_the_four_core_fields():
    """必填四项是硬约定，契约里必须体现，否则前端会拿到缺字段的卡片。"""
    schema = json.loads(render("vod-item", EXPORTS["vod-item"]))
    assert set(schema["required"]) == {"vod_id", "vod_name", "vod_pic", "vod_remarks"}
