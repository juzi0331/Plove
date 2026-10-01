"""后台批量采集任务与异步调度 API。"""

import asyncio
import time
import uuid
from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ..engine.rule_manager import rule_manager
from ..engine.scraper import UniversalScraper
from ..core.log import get_logger

logger = get_logger("tasks")

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# 内存任务字典
_TASKS: dict[str, dict[str, Any]] = {}


class BatchScrapeRequest(BaseModel):
    site_keys: Optional[list[str]] = None
    actions: list[str] = ["home"]


async def _run_batch_scrape(task_id: str, site_keys: list[str], actions: list[str]):
    _TASKS[task_id]["status"] = "running"
    results = {}
    for key in site_keys:
        results[key] = {}
        try:
            rule = rule_manager.get_rule(key)
            scraper = UniversalScraper(rule)
            for action in actions:
                try:
                    res = await scraper.execute(action)
                    results[key][action] = {"ok": True, "count": len(res.get("recommend", []) or res.get("videos", []) or res.get("categories", []))}
                except Exception as exc:
                    results[key][action] = {"ok": False, "error": str(exc)}
        except Exception as exc:
            results[key] = {"error": str(exc)}

    _TASKS[task_id]["status"] = "completed"
    _TASKS[task_id]["completed_at"] = time.time()
    _TASKS[task_id]["results"] = results
    logger.info("后台批量任务 %s 完成", task_id)


@router.post("/batch")
async def create_batch_task(req: BatchScrapeRequest, bg_tasks: BackgroundTasks):
    target_keys = req.site_keys or [r.key for r in rule_manager.list_rules()]
    task_id = str(uuid.uuid4())[:8]
    _TASKS[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "created_at": time.time(),
        "site_keys": target_keys,
        "actions": req.actions,
        "results": None,
    }
    bg_tasks.add_task(_run_batch_scrape, task_id, target_keys, req.actions)
    return {
        "ok": True,
        "data": {
            "task_id": task_id,
            "status": "pending",
            "sites_count": len(target_keys),
        },
        "error": None,
    }


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "data": None, "error": {"code": "NOT_FOUND", "message": f"任务不存在: {task_id}"}}
    return {"ok": True, "data": task, "error": None}
