"""crawler_service 命令行独立调试与管理工具。

用法示例：
  python cli.py list-rules
  python cli.py run --site ai2048 --action home
  python cli.py run --site ai2048 --action category --tid 1 --page 1
  python cli.py validate-rule rules/ai2048.json
  python cli.py serve --port 8088
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 强制 UTF-8，彻底解决 Windows GBK 控制台中文乱码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 确保父路径在 sys.path 中以支持直接运行 cli.py
current_dir = Path(__file__).resolve().parent
if str(current_dir.parent) not in sys.path:
    sys.path.insert(0, str(current_dir.parent))


from crawler.service.config import settings
from crawler.service.engine.models import SiteRule
from crawler.service.engine.rule_manager import rule_manager
from crawler.service.engine.scraper import UniversalScraper


def print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


async def handle_run(args: argparse.Namespace) -> None:
    try:
        rule = rule_manager.get_rule(args.site)
    except Exception as exc:
        print_json({"ok": False, "data": None, "error": {"code": "SITE_NOT_FOUND", "message": str(exc)}})
        return

    scraper = UniversalScraper(rule)
    params = {}
    if args.tid:
        params["tid"] = args.tid
    if args.page:
        params["page"] = args.page
    if args.id:
        params["id"] = args.id
    if args.ep:
        params["ep"] = args.ep
    if args.play_id:
        params["play_id"] = args.play_id
    if args.line:
        params["line"] = args.line
    if args.kw:
        params["kw"] = args.kw

    try:
        result = await scraper.execute(args.action, **params)
        print_json({"ok": True, "data": result, "error": None})
    except Exception as exc:
        print_json({"ok": False, "data": None, "error": {"code": "SCRAPE_FAILED", "message": str(exc)}})


def handle_list_rules(args: argparse.Namespace) -> None:
    rules = rule_manager.list_rules()
    data = [
        {
            "key": r.key,
            "name": r.name,
            "base_url": r.base_url,
            "data_type": r.data_type,
            "version": r.version,
        }
        for r in rules
    ]
    print_json({"ok": True, "data": data, "error": None})


def handle_validate_rule(args: argparse.Namespace) -> None:
    path = Path(args.file)
    if not path.is_file():
        print_json({"ok": False, "error": f"文件不存在: {path}"})
        return

    try:
        content = path.read_text(encoding="utf-8")
        raw = json.loads(content)
        rule = SiteRule.model_validate(raw)
        print_json({
            "ok": True,
            "message": f"规则校验通过: {rule.name} (key={rule.key})",
            "rule": rule.model_dump(),
        })
    except Exception as exc:
        print_json({"ok": False, "error": f"校验失败: {exc}"})


def handle_serve(args: argparse.Namespace) -> None:
    import uvicorn
    port = args.port or settings.PORT
    host = args.host or settings.HOST
    print(f"正在启动 Crawler Service: http://{host}:{port}")
    uvicorn.run("crawler.service.main:app", host=host, port=port, reload=args.reload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plove Universal Crawler CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run 子命令
    run_parser = subparsers.add_parser("run", help="执行采集动作")
    run_parser.add_argument("--site", required=True, help="站点 key，如 ai2048")
    run_parser.add_argument("--action", required=True, choices=["meta", "home", "category", "detail", "play", "search"], help="执行的动作")
    run_parser.add_argument("--id", help="影片 ID")
    run_parser.add_argument("--tid", help="分类 ID")
    run_parser.add_argument("--page", type=int, default=1, help="页码")
    run_parser.add_argument("--ep", type=int, default=1, help="集号")
    run_parser.add_argument("--play-id", help="播放标识")
    run_parser.add_argument("--line", help="线路标识")
    run_parser.add_argument("--kw", help="搜索关键词")

    # list-rules 子命令
    subparsers.add_parser("list-rules", help="列出已加载的站点规则")

    # validate-rule 子命令
    val_parser = subparsers.add_parser("validate-rule", help="校验规则文件语法")
    val_parser.add_argument("file", help="规则文件路径")

    # serve 子命令
    serve_parser = subparsers.add_parser("serve", help="启动 HTTP API 微服务")
    serve_parser.add_argument("--host", default=None, help="监听主机")
    serve_parser.add_argument("--port", type=int, default=None, help="监听端口")
    serve_parser.add_argument("--reload", action="store_true", help="热重载模式")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(handle_run(args))
    elif args.command == "list-rules":
        handle_list_rules(args)
    elif args.command == "validate-rule":
        handle_validate_rule(args)
    elif args.command == "serve":
        handle_serve(args)


if __name__ == "__main__":
    main()
