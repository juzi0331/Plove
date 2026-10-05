"""采集器脚本合规安全审计与执行环境公共工具箱。

供后端管理后台 (backend) 与爬虫控制微服务 (crawler.service) 统一使用，
消除两端重复编写 AST 黑名单与环境变量注入逻辑。
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

#: 禁止导入的高危系统级模块
DANGEROUS_MODULES: frozenset[str] = frozenset({
    "subprocess",
    "ctypes",
    "socket",
    "pty",
    "multiprocessing",
    "shutil",
    "importlib",
    "pathlib",
    "tempfile",
    "posix",
    "nt",
    "builtins",
    "inspect",
})

#: 禁止直接调用的高危系统方法或属性
DANGEROUS_ATTRIBUTES: frozenset[str] = frozenset({
    "system",
    "popen",
    "exec",
    "eval",
    "spawn",
    "fork",
    "kill",
    "remove",
    "unlink",
    "rmdir",
    "mkdir",
    "rename",
    "replace",
    "chmod",
    "open",
})

#: 禁止直接引用的内置危险全局函数
DANGEROUS_BUILTIN_NAMES: frozenset[str] = frozenset({
    "eval",
    "exec",
    "__import__",
    "open",
    "compile",
})


def audit_script_ast(code: str) -> tuple[bool, str | None]:
    """静态检查 Python 源码是否包含语法错误或违规调用危险指令。
    
    返回: (passed, error_message)
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"Python 语法错误（第 {exc.lineno} 行）: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if root_pkg in DANGEROUS_MODULES:
                    return False, f"禁止导入受限模块: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg in DANGEROUS_MODULES:
                    return False, f"禁止导入受限模块: {node.module}"
        elif isinstance(node, ast.Attribute):
            if node.attr in DANGEROUS_ATTRIBUTES:
                return False, f"禁止调用受限属性或函数: {node.attr}"
        elif isinstance(node, ast.Name):
            if node.id in DANGEROUS_BUILTIN_NAMES:
                return False, f"禁止直接使用内置危险函数: {node.id}"

    return True, None


#: 允许透传给子进程的白名单系统环境变量
_SAFE_ENV_KEYS: frozenset[str] = frozenset({
    "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONHOME", "LANG", "LC_ALL",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "APPDATA", "LOCALAPPDATA",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "COMSPEC", "PATHEXT",
})


def get_crawler_runner_env() -> dict[str, str]:
    """构建确保子进程运行并正确加载 crawler_kit 的隔离白名单环境变量。"""
    # 严格采用白名单，杜绝将父进程敏感配置（密钥、令牌、数据库连接）泄漏给第三方采集脚本
    env: dict[str, str] = {
        k: v for k, v in os.environ.items() if k.upper() in _SAFE_ENV_KEYS
    }
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    # 寻址 crawler 根目录并注入 PYTHONPATH 和 CRAWLER_KIT_PATH
    current_file = Path(__file__).resolve()
    # current_file: crawler/crawler_kit/audit.py -> parents[1] is crawler/
    crawler_dir = current_file.parents[1]
    project_root = crawler_dir.parent

    if crawler_dir.is_dir():
        crawler_root = str(crawler_dir)
        env["CRAWLER_KIT_PATH"] = crawler_root
        existing_pp = env.get("PYTHONPATH", "")
        pp_parts = [crawler_root, str(project_root)]
        if existing_pp:
            pp_parts.append(existing_pp)
        env["PYTHONPATH"] = os.pathsep.join(pp_parts)

    return env
