#!/usr/bin/env python
"""测试用的假爬虫：不联网、不依赖 crawler_kit，只按协议吐信封。

它的价值在于**真的被当子进程跑起来** —— 所以硬超时、脏输出、错误码翻译、
契约拒收这些路径测的都是真实代码，而不是被 mock 掉的东西。

用环境变量 ``FAKE_MODE`` 触发各种情况：

| 值 | 行为 |
| --- | --- |
| （空） | 一切正常 |
| `timeout` | 卡住不返回（测硬超时） |
| `error` | 返回 `ok:false` + `BLOCKED`（测错误码翻译） |
| `garbage` | 输出非 JSON（测解析兜底） |
| `bad_data` | 输出违反契约的 data（测"不合格就拒收"） |
| `meta_broken` | 只有 `meta` 失败（测列表跳过坏源） |
| `slow` | 先睡 `FAKE_SLEEP` 秒（默认 0.5）再正常返回（测并发与合并） |

失败模式**只作用于非 meta 命令**，这样测试能确定到底是哪一层出的错。

## 另一个环境变量：``FAKE_COUNTER``

设成文件路径时，每次被调起来就往里**追加一行命令名**。
这是验证"到底真跑了几次"的唯一硬手段 —— 缓存和合并这两个东西，
光看响应内容看不出区别（缓存命中的响应和有网抓的响应看起来一模一样）。
"""

from __future__ import annotations

import json
import os
import sys
import time

KEY = "fake"
CAPABILITIES = ("meta", "home", "category", "detail", "play", "selftest")
#: 故意**不**支持 search —— 用来验证"该源不支持"不会被伪装成"搜到 0 条"

VOD = {
    "vod_id": "1",
    "vod_name": "测试影片",
    "vod_pic": "https://example.test/1.jpg",
    "vod_remarks": "全2集",
}


def _payload(command: str, options: dict) -> dict:
    if command == "meta":
        return {
            "key": KEY,
            "name": "假站点",
            "version": "1.0.0",
            "base_url": "https://example.test",
            "mode": "direct",
            "capabilities": list(CAPABILITIES),
            "play_format": ["m3u8"],
        }
    if command == "home":
        return {"categories": [{"tid": "1", "name": "分类一"}], "recommend": [VOD]}
    if command == "category":
        return {"videos": [VOD], "page": int(options.get("page") or 1), "has_more": False}
    if command == "detail":
        return {
            "video": VOD,
            "desc": "简介",
            "episodes": [{"ep_index": 1, "ep_name": "第1集", "play_id": "p1"}],
            "lines": [{"line": 1, "name": "线路1", "count": 1}],
        }
    if command == "play":
        # 把"有没有收到 play_id"写进 url 里：后端有没有真的把它转下去，
        # 从响应体上一眼就能看出来（否则只能去翻 argv）。
        source = "via-play-id" if options.get("play_id") else "via-detail"
        return {
            "url": f"https://example.test/{source}/index.m3u8",
            "format": "m3u8",
            "headers": {"Referer": "https://example.test/"},
        }
    if command == "selftest":
        return {"selectors": {"home.card": 1}}
    raise ValueError(f"未知命令: {command}")


def _parse_argv(argv: list[str]) -> tuple[str, dict]:
    command = "meta"
    if argv and not argv[0].startswith("-"):
        command = argv.pop(0)
    options: dict[str, str | None] = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token.startswith("--"):
            value = None
            if index + 1 < len(argv) and not argv[index + 1].startswith("--"):
                value = argv[index + 1]
                index += 1
            options[token[2:]] = value
        index += 1
    return command, options


def _emit(ok: bool, data=None, code: str | None = None, message: str | None = None) -> None:
    error = None if ok else {"code": code, "message": message}
    print(json.dumps({"ok": ok, "data": data, "error": error}, ensure_ascii=False))


def _count(command: str) -> None:
    """往 FAKE_COUNTER 指向的文件追加一行。没设就什么都不做。"""
    path = os.environ.get("FAKE_COUNTER")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(command + "\n")


def main() -> int:
    mode = os.environ.get("FAKE_MODE", "")
    command, options = _parse_argv(sys.argv[1:])
    is_meta = command == "meta"

    _count(command)

    if mode == "timeout":
        time.sleep(60)
    elif mode == "slow" and not is_meta:
        time.sleep(float(os.environ.get("FAKE_SLEEP", "0.5")))
    elif mode == "meta_broken" and is_meta:
        _emit(False, code="BLOCKED", message="假站点说 meta 也拿不到")
        return 0
    elif mode == "error" and not is_meta:
        _emit(False, code="BLOCKED", message="被假站点拦住")
        return 0
    elif mode == "garbage" and not is_meta:
        print("这不是 JSON")
        return 0
    elif mode == "bad_data" and not is_meta:
        # 缺 vod_id 这类必填字段 —— 契约必须把它挡住
        _emit(True, data={"recommend": [{"vod_name": "缺少必填字段"}]})
        return 0

    if command not in CAPABILITIES:
        _emit(False, code="UNSUPPORTED", message=f"该源不支持 {command}")
        return 0

    _emit(True, data=_payload(command, options))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
