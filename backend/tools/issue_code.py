#!/usr/bin/env python
"""签发激活码。

用法::

    python tools/issue_code.py --days 30
    python tools/issue_code.py --hours 24 --count 5 --note "第一批试用"
    python tools/issue_code.py --days 7 --note "给老王"

时长只存**小时**，天数是换算过来的 —— 库里只有一种单位，就不会出现
"这个字段到底是天还是小时"这种经典歧义。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import force_utf8  # noqa: E402

from app.db.session import session_scope  # noqa: E402
from app.services import activation_service  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    force_utf8()
    parser = argparse.ArgumentParser(description="签发激活码")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--hours", type=int, help="时长（小时）")
    group.add_argument("--days", type=int, help="时长（天），与 --hours 二选一")
    parser.add_argument("--count", type=int, default=1, help="签发几个，默认 1")
    parser.add_argument("--note", default="", help="备注：发给谁 / 哪一批")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.days is not None:
        hours = args.days * 24
    elif args.hours is not None:
        hours = args.hours
    else:
        print("必须给 --days 或 --hours（不知道要多长时长就没法发码）")
        return 2

    if args.count < 1:
        print("--count 至少是 1")
        return 2

    issued: list[str] = []
    with session_scope() as session:
        for _ in range(args.count):
            record = activation_service.issue_code(session, duration_hours=hours, note=args.note)
            issued.append(record.code)

    print(f"已签发 {len(issued)} 个码，时长 {hours} 小时（{hours / 24:g} 天）")
    for code in issued:
        print(f"  {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
