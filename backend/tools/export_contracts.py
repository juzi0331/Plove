#!/usr/bin/env python
"""契约导出 CLI。

用法::

    python tools/export_contracts.py           # 写出 contracts/schemas/*.json
    python tools/export_contracts.py --check   # 只比对不写；有过期就退出码 1（CI 用）

逻辑都在 :mod:`app.contracts`，这里只负责命令行包装。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import force_utf8  # noqa: E402

from app.contracts import stale_contracts, write_contracts  # noqa: E402
from app.core.config import get_settings  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    force_utf8()
    parser = argparse.ArgumentParser(description="把 Pydantic 模型导出成 contracts/schemas/*.json")
    parser.add_argument("--check", action="store_true", help="只比对不写，有过期就退出码 1")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    out_dir = get_settings().schemas_dir

    if args.check:
        stale = stale_contracts(out_dir)
        if stale:
            print("契约已过期，请重新运行 python tools/export_contracts.py：")
            for name in stale:
                print(f"  - {name}")
            return 1
        print(f"契约一致（{out_dir}）")
        return 0

    written = write_contracts(out_dir)
    print(f"已写出 {len(written)} 个契约到 {out_dir}")
    for name in written:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
