"""采集器脚本管理服务：语法检查、安全合规审计、冒烟试运行、热落盘与查看/删除。

规矩：
* 不 import fastapi（services 层的硬规矩），要报错就抛 AppError。
* 威胁模型是代码与协议合规，防止恶意指令或破坏系统。
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.crawler.runner import SITE_KEY_PATTERN
from app.schemas.admin_site_control import (
    CrawlerCodePayload,
    CrawlerValidateResult,
)
from app.schemas.site import SiteMeta

logger = get_logger(__name__)

#: 危险模块与属性黑名单
_DANGEROUS_MODULES = frozenset({
    "subprocess",
    "ctypes",
    "socket",
    "pty",
    "multiprocessing",
    "shutil",
    "importlib",
})

_DANGEROUS_ATTRIBUTES = frozenset({
    "system",
    "popen",
    "exec",
    "eval",
    "spawn",
    "fork",
    "kill",
})


def _audit_ast(code: str) -> tuple[bool, str | None]:
    """静态检查代码是否包含 SyntaxError 或危险调用。"""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"Python 语法错误（第 {exc.lineno} 行）: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if root_pkg in _DANGEROUS_MODULES:
                    return False, f"禁止导入受限模块: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg in _DANGEROUS_MODULES:
                    return False, f"禁止导入受限模块: {node.module}"
        elif isinstance(node, ast.Attribute):
            if node.attr in _DANGEROUS_ATTRIBUTES:
                return False, f"禁止调用受限属性或函数: {node.attr}"
        elif isinstance(node, ast.Name):
            if node.id in {"eval", "exec", "__import__"}:
                return False, f"禁止直接使用内置危险函数: {node.id}"

    return True, None


def _probe_meta(script_path: Path, python_exe: str | None = None) -> tuple[bool, SiteMeta | None, str | None]:
    """在隔离子进程中试跑一次 meta 命令。"""
    py = python_exe or sys.executable
    argv = [py, str(script_path), "meta"]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    # 确保隔离临时文件子进程也能加载并导入 crawler_kit
    crawler_dir = Path(__file__).resolve().parents[3] / "crawler"
    if crawler_dir.is_dir():
        crawler_root = str(crawler_dir)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{crawler_root}{os.pathsep}{existing_pp}" if existing_pp else crawler_root

    try:
        proc = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4.0,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, None, "试运行 meta 超时（超过 4 秒未返回）"
    except Exception as exc:
        return False, None, f"无法执行子进程测试: {exc}"

    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or f"进程非正常退出（退出码 {proc.returncode}）"
        return False, None, f"运行失败: {err_msg}"

    stdout = proc.stdout.strip()
    if not stdout:
        return False, None, f"爬虫没有输出任何内容，stderr: {proc.stderr.strip()}"

    # 尝试按 JSON 信封解析
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return False, None, f"爬虫 stdout 不是合法 JSON: {stdout[:200]}"

    if not isinstance(envelope, dict) or not envelope.get("ok"):
        err = envelope.get("error") if isinstance(envelope, dict) else None
        return False, None, f"爬虫返回失败信封: {err or stdout[:200]}"

    data = envelope.get("data")
    if not isinstance(data, dict):
        return False, None, "信封内的 data 不是字典对象"

    try:
        meta = SiteMeta(**data)
        return True, meta, None
    except Exception as exc:
        return False, None, f"meta 数据不符合 SiteMeta 契约: {exc}"


def validate_crawler_code(
    code: str,
    sites_dir: Path,
    python_exe: str | None = None,
    suggested_key: str | None = None,
) -> CrawlerValidateResult:
    """全面校验采集器源码（AST 语法 + 审计 + 协议冒烟）。"""
    checks: list[str] = []

    # 1. AST 语法与危险特征审计
    ast_ok, ast_err = _audit_ast(code)
    if not ast_ok:
        return CrawlerValidateResult(
            valid=False,
            key=suggested_key or "unknown",
            error=ast_err,
            checks=checks,
        )
    checks.append("语法与安全审计通过")

    # 2. 临时写出并试跑 meta 命令
    with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tmp:
        tmp.write(code)
        tmp_path = Path(tmp.name)

    try:
        meta_ok, meta, meta_err = _probe_meta(tmp_path, python_exe=python_exe)
        if not meta_ok or meta is None:
            return CrawlerValidateResult(
                valid=False,
                key=suggested_key or "unknown",
                error=meta_err,
                checks=checks,
            )
        checks.append("协议冒烟测试 meta 通过")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    key = meta.key
    if suggested_key and suggested_key != key:
        return CrawlerValidateResult(
            valid=False,
            key=suggested_key,
            error=f"指定的 key ({suggested_key}) 与脚本声明的 key ({key}) 不一致",
            checks=checks,
        )

    if not SITE_KEY_PATTERN.match(key):
        return CrawlerValidateResult(
            valid=False,
            key=key,
            error=f"站点 key 格式不合法: {key}",
            checks=checks,
        )
    checks.append(f"站点 key 校验通过: {key}")

    return CrawlerValidateResult(
        valid=True,
        key=key,
        meta=meta,
        error=None,
        checks=checks,
    )


def save_crawler(
    sites_dir: Path,
    key: str,
    code: str,
    overwrite: bool = False,
    python_exe: str | None = None,
) -> SiteMeta:
    """保存并热部署采集器脚本。"""
    if not SITE_KEY_PATTERN.match(key):
        raise AppError(ErrorCode.BAD_REQUEST, f"非法的站点 key: {key}")

    target_file = sites_dir / f"{key}.py"
    if target_file.exists() and not overwrite:
        raise AppError(ErrorCode.CONFLICT, f"采集器 {key} 已经存在，若需替换请开启覆盖选项")

    # 先验证
    res = validate_crawler_code(code, sites_dir, python_exe=python_exe, suggested_key=key)
    if not res.valid or res.meta is None:
        raise AppError(ErrorCode.BAD_REQUEST, f"采集器校验失败: {res.error}")

    try:
        sites_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(code, encoding="utf-8")
        logger.info("已成功保存采集器脚本: %s", target_file)
    except Exception as exc:
        raise AppError(ErrorCode.INTERNAL, f"保存脚本失败: {exc}") from exc

    return res.meta


def get_crawler_code(sites_dir: Path, key: str) -> CrawlerCodePayload:
    """读取指定采集器的源代码。"""
    if not SITE_KEY_PATTERN.match(key):
        raise AppError(ErrorCode.BAD_REQUEST, f"非法的站点 key: {key}")

    target_file = sites_dir / f"{key}.py"
    if not target_file.is_file():
        raise AppError(ErrorCode.NOT_FOUND, f"采集器不存在: {key}")

    code = target_file.read_text(encoding="utf-8", errors="replace")
    mtime = target_file.stat().st_mtime
    updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return CrawlerCodePayload(key=key, code=code, updated_at=updated_at)


def delete_crawler(sites_dir: Path, key: str) -> None:
    """删除指定采集器。"""
    if not SITE_KEY_PATTERN.match(key):
        raise AppError(ErrorCode.BAD_REQUEST, f"非法的站点 key: {key}")

    target_file = sites_dir / f"{key}.py"
    if not target_file.is_file():
        raise AppError(ErrorCode.NOT_FOUND, f"采集器不存在: {key}")

    target_file.unlink()
    logger.info("已删除采集器脚本: %s", target_file)
