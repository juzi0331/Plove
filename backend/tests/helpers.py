"""测试用的小工具。

单独放一个文件而不是塞进 ``conftest.py``：``conftest`` 是给 pytest 收集夹具用的，
放纯函数进去会让"这个函数到底是不是夹具"变得含糊 —— 而这类含糊最后都会
变成"怎么 import 都不对"。
"""

from __future__ import annotations

from pathlib import Path


def crawler_calls(path: Path, command: str | None = None) -> int:
    """数一数假爬虫被调了多少次；给了 ``command`` 就只数那一个命令。

    缓存与 singleflight 只能靠"真跑了几次"来验证 —— 它们的响应内容
    和有网抓的**一模一样**，从结果上是看不出来的。
    """
    if not path.exists():
        return 0
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return len(lines) if command is None else sum(1 for line in lines if line == command)
