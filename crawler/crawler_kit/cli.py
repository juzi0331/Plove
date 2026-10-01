"""命令行入口：参数解析 + 统一信封 + 异常兜底。

硬规矩（照抄协议，不要改动）：

* **stdout 只输出一行 JSON**，任何日志/栈一律走 stderr。
* **退出码永远是 0**，失败用 ``ok:false`` 表达；超时由调用方 kill。
* 未实现的命令必须报 ``UNSUPPORTED``，**不允许静默返回空列表** ——
  "该源不支持搜索"和"搜到 0 条"对用户是两件完全不同的事。
"""

from __future__ import annotations

import inspect
import json
import sys
import traceback

from . import log
from .clean import to_int
from .errors import NOT_FOUND, UNKNOWN, CrawlerError, unsupported

#: 命令行已声明支持的参数（``--key value`` 形式）。
#: ``line`` 是多线路源用的（同一部剧有多个播放线路，分别选播）。
#: ``play_id`` 是**加速通道**：详情里每集都带着它，上层原样传回来，
#: 源就可以省掉一次"为了找到这一集而重抓详情页"。（命令行写 ``--play-id``，
#: 横线在这里会被换成下划线。）
KNOWN_OPTIONS = ("tid", "page", "kw", "id", "ep", "line", "play_id")

#: 需要转成整数的参数及其默认值。
#: 注意 ``play_id`` **不在这里** —— 它是不透明定位符（长这样
#: ``/play/318185-41-2946527.html``），转成整数就把它毁了。
INT_OPTIONS = {"page": 1, "ep": 1, "line": 1}


def force_utf8() -> None:
    """把 stdout/stderr 强制成 UTF-8。

    Windows 上 ``sys.stdout.encoding`` 默认是 **GBK**，直接写中文会让后端
    按 UTF-8 解析时炸掉 —— 典型的"本地绿、上传炸"。JSON 的交换编码就是
    UTF-8（RFC 8259），所以这里必须写死。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # 测试里的 StringIO 等
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - 不可重配置的流
            pass


def parse_argv(argv):
    """``['category', '--tid', '27', '--page', '2']`` -> ``('category', {...})``"""
    argv = list(argv or [])
    command = "meta"
    if argv and not argv[0].startswith("-"):
        command = argv.pop(0)

    options = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token.startswith("--"):
            name = token[2:].replace("-", "_")
            value = None
            if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
                value = argv[index + 1]
                index += 1
            options[name] = value
        index += 1
    return command, options


def emit(data) -> None:
    print(json.dumps({"ok": True, "data": data, "error": None}, ensure_ascii=False))


def emit_error(code: str, message: str) -> None:
    print(
        json.dumps(
            {"ok": False, "data": None, "error": {"code": code, "message": message}},
            ensure_ascii=False,
        )
    )


def dispatch(site, command: str, options: dict):
    handler = getattr(site, command, None)
    if not command.isidentifier() or command.startswith("_") or not callable(handler):
        raise unsupported(f"未知命令: {command}")

    capabilities = getattr(site, "capabilities", None)
    if capabilities is not None and command not in capabilities:
        raise unsupported(f"该源不支持 {command}")

    signature = inspect.signature(handler)
    accepted = {
        name for name in signature.parameters if name not in ("self", "cls")
    }

    kwargs = {}
    for name in KNOWN_OPTIONS:
        if name in accepted and options.get(name) is not None:
            kwargs[name] = options[name]

    for name, default in INT_OPTIONS.items():
        if name in kwargs:
            kwargs[name] = to_int(kwargs[name], default)

    unknown = sorted(set(options) - set(KNOWN_OPTIONS))
    if unknown:
        log.warn(f"忽略未知参数: {', '.join('--' + name for name in unknown)}")

    for name, parameter in signature.parameters.items():
        if name in ("self", "cls"):
            continue
        if parameter.default is inspect.Parameter.empty and name not in kwargs:
            raise CrawlerError(NOT_FOUND, f"缺少必填参数 --{name}")

    return handler(**kwargs)


def run(site, argv=None) -> int:
    """执行一次命令，永远返回 0。"""
    force_utf8()
    command, options = parse_argv(argv if argv is not None else sys.argv[1:])
    try:
        emit(dispatch(site, command, options))
    except CrawlerError as exc:
        log.error(f"{command} 失败 {exc}")
        emit_error(exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001 - 兜底，绝不允许崩栈污染 stdout
        log.error(f"{command} 未预期异常:\n{traceback.format_exc()}")
        emit_error(UNKNOWN, f"{type(exc).__name__}: {exc}")
    return 0


def main(site) -> int:
    return run(site)
