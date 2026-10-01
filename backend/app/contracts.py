"""契约导出：Pydantic 模型 → ``contracts/schemas/*.json``。

**唯一事实源是 :mod:`app.schemas` 下的 Pydantic 模型**，导出的 JSON 是生成物，
供另外两端使用：

* 前端：据它生成 TS 类型；
* 爬虫：只用标准库，读同一份 JSON 做最小校验（``required`` / ``type`` / ``enum``）。

所以 **不要手改 contracts/schemas 里的文件**。改完模型重新导出，并把生成物一起提交。
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.schemas import EXPORTS

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID_BASE = "https://plove.local/schemas/"


def build_schema(stem: str, model: type[BaseModel]) -> dict:
    """给 Pydantic 生成的 schema 补上 dialect 与稳定 ``$id``。"""
    schema: dict = {"$schema": SCHEMA_DIALECT, "$id": f"{SCHEMA_ID_BASE}{stem}.json"}
    schema.update(model.model_json_schema())
    return schema


def render(stem: str, model: type[BaseModel]) -> str:
    """渲染成写入文件的那段文本（带结尾换行，避免编辑器噪音）。"""
    return json.dumps(build_schema(stem, model), ensure_ascii=False, indent=2) + "\n"


def write_contracts(out_dir: Path) -> list[str]:
    """写出全部契约，返回写出的文件名。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, model in EXPORTS.items():
        path = out_dir / f"{stem}.json"
        path.write_text(render(stem, model), encoding="utf-8")
        written.append(path.name)
    return written


def stale_contracts(out_dir: Path) -> list[str]:
    """返回**与模型不一致或缺失**的契约文件名；空列表表示契约是最新的。"""
    stale = []
    for stem, model in EXPORTS.items():
        path = out_dir / f"{stem}.json"
        if not path.exists() or path.read_text(encoding="utf-8") != render(stem, model):
            stale.append(path.name)
    return stale
