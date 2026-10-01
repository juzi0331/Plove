"""外部 Python 采集器脚本导入与全链路测试引擎。

支持对用户/外部 AI 编写的爬虫脚本进行完整合规性与真实链路试跑：
1. AST 安全与合规审计
2. 子进程 meta 冒烟测试
3. home 动作实测（验证推荐与分类）
4. detail 动作采样穿透测试（自动取首页第 1 部片）
5. play 动作播放嗅探实测（自动取第 1 集）
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Optional
from pydantic import BaseModel

from ..core.log import get_logger

logger = get_logger("script_tester")

_DANGEROUS_MODULES = frozenset({
    "subprocess", "ctypes", "socket", "pty", "multiprocessing", "shutil", "importlib",
})
_DANGEROUS_ATTRIBUTES = frozenset({
    "system", "popen", "exec", "eval", "spawn", "fork", "kill",
})


class StepTestResult(BaseModel):
    name: str
    passed: bool
    duration_ms: float
    output_summary: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Any] = None


class FullSuiteReport(BaseModel):
    all_passed: bool
    key: str
    site_name: str
    steps: list[StepTestResult]
    can_deploy: bool


class ScriptTester:
    """采集器脚本测试器。"""

    def __init__(self, code: str, custom_key: Optional[str] = None) -> None:
        self.code = code
        self.custom_key = custom_key or "test_site"

    def audit_ast(self) -> tuple[bool, Optional[str]]:
        try:
            tree = ast.parse(self.code)
        except SyntaxError as exc:
            return False, f"Python 语法错误 (第 {exc.lineno} 行): {exc.msg}"

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
                    return False, f"禁止调用受限方法/属性: {node.attr}"
            elif isinstance(node, ast.Name):
                if node.id in {"eval", "exec", "__import__"}:
                    return False, f"禁止直接使用危险内置函数: {node.id}"

        return True, None

    def run_subcommand(self, script_path: Path, command: str, **options: Any) -> tuple[bool, Optional[dict], Optional[str]]:
        argv = [sys.executable, str(script_path), command]
        for k, v in options.items():
            if v is not None:
                argv.extend([f"--{k}", str(v)])

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # 注入 crawler_kit 所在目录
        crawler_dir = Path(__file__).resolve().parents[2] / "crawler"
        if crawler_dir.is_dir():
            crawler_root = str(crawler_dir)
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{crawler_root}{os.pathsep}{existing}" if existing else crawler_root

        try:
            proc = subprocess.run(  # noqa: S603
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15.0,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return False, None, f"运行 {command} 超时 (超过 15 秒)"
        except Exception as exc:
            return False, None, f"执行异常: {exc}"

        if proc.returncode != 0:
            err = proc.stderr.strip() or f"非正常退出码 {proc.returncode}"
            return False, None, err

        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if not lines:
            return False, None, f"进程未输出任何信封内容，stderr: {proc.stderr.strip()}"

        first_line = lines[-1]
        try:
            envelope = json.loads(first_line)
        except Exception as exc:
            return False, None, f"输出的不是合规 JSON 信封: {exc} (末行内容: {first_line[:120]})"

        if not isinstance(envelope, dict):
            return False, None, "输出 JSON 格式不为对象信封"

        if not envelope.get("ok"):
            err_dict = envelope.get("error") or {}
            msg = err_dict.get("message") if isinstance(err_dict, dict) else str(err_dict)
            return False, None, f"信封返回错误: {msg}"

        return True, envelope.get("data"), None

    def run_full_suite(self) -> FullSuiteReport:
        steps: list[StepTestResult] = []
        site_name = self.custom_key
        detected_key = self.custom_key

        # 1. AST 安全审计
        t0 = time.perf_counter()
        ast_ok, ast_err = self.audit_ast()
        steps.append(StepTestResult(
            name="1. AST 语法与安全合规审计",
            passed=ast_ok,
            duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            output_summary="未发现非法模块或危险调用" if ast_ok else None,
            error=ast_err,
        ))
        if not ast_ok:
            return FullSuiteReport(all_passed=False, key=detected_key, site_name=site_name, steps=steps, can_deploy=False)

        # 写入临时文件测试
        with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tmp:
            tmp.write(self.code)
            tmp_path = Path(tmp.name)

        try:
            # 2. 测试 meta 命令
            t0 = time.perf_counter()
            meta_ok, meta_data, meta_err = self.run_subcommand(tmp_path, "meta")
            if meta_ok and isinstance(meta_data, dict):
                detected_key = meta_data.get("key", detected_key)
                site_name = meta_data.get("name", site_name)
                summary = f"站点名: {site_name}, Key: {detected_key}, 模式: {meta_data.get('mode', 'direct')}"
            else:
                summary = None

            steps.append(StepTestResult(
                name="2. 协议冒烟测试 (meta)",
                passed=meta_ok,
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                output_summary=summary,
                error=meta_err,
                data=meta_data,
            ))
            if not meta_ok:
                return FullSuiteReport(all_passed=False, key=detected_key, site_name=site_name, steps=steps, can_deploy=False)

            # 3. 测试 home 命令
            t0 = time.perf_counter()
            home_ok, home_data, home_err = self.run_subcommand(tmp_path, "home")
            sample_vod = None
            if home_ok and isinstance(home_data, dict):
                recs = home_data.get("recommend", [])
                cats = home_data.get("categories", [])
                summary = f"发现 {len(cats)} 个分类，成功抓取 {len(recs)} 部首页推荐影片"
                if recs and isinstance(recs[0], dict):
                    sample_vod = recs[0]
            else:
                summary = None

            steps.append(StepTestResult(
                name="3. 首页数据抓取测试 (home)",
                passed=home_ok,
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                output_summary=summary,
                error=home_err,
                data=home_data,
            ))
            if not home_ok or not sample_vod:
                return FullSuiteReport(all_passed=False, key=detected_key, site_name=site_name, steps=steps, can_deploy=False)

            # 4. 测试 detail 穿透
            t0 = time.perf_counter()
            vod_id = sample_vod.get("vod_id")
            detail_ok, detail_data, detail_err = self.run_subcommand(tmp_path, "detail", id=vod_id)
            sample_ep = None
            if detail_ok and isinstance(detail_data, dict):
                episodes = detail_data.get("episodes", [])
                summary = f"影片《{sample_vod.get('vod_name')}》穿透成功，提取到 {len(episodes)} 个剧集"
                if episodes and isinstance(episodes[0], dict):
                    sample_ep = episodes[0]
            else:
                summary = None

            steps.append(StepTestResult(
                name="4. 影片详情穿透测试 (detail)",
                passed=detail_ok,
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                output_summary=summary,
                error=detail_err,
                data=detail_data,
            ))
            if not detail_ok or not sample_ep:
                # 即使没有 detail，也可以允许有条件的部署，但标 false
                return FullSuiteReport(all_passed=False, key=detected_key, site_name=site_name, steps=steps, can_deploy=False)

            # 5. 测试 play 嗅探
            t0 = time.perf_counter()
            play_ok, play_data, play_err = self.run_subcommand(
                tmp_path,
                "play",
                id=vod_id,
                ep=sample_ep.get("ep_index", 1),
                play_id=sample_ep.get("play_id"),
                line=sample_ep.get("line"),
            )
            if play_ok and isinstance(play_data, dict):
                stream_url = play_data.get("url", "")
                summary = f"成功提取第 1 集播放直链 ({play_data.get('format', 'm3u8')}): {stream_url[:70]}..."
            else:
                summary = None

            steps.append(StepTestResult(
                name="5. 播放地址嗅探测试 (play)",
                passed=play_ok,
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                output_summary=summary,
                error=play_err,
                data=play_data,
            ))

            all_passed = all(s.passed for s in steps)
            return FullSuiteReport(
                all_passed=all_passed,
                key=detected_key,
                site_name=site_name,
                steps=steps,
                can_deploy=all_passed,
            )

        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass
