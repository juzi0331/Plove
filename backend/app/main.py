"""应用组装。

这里**只做组装**：建 app、挂中间件、注册异常处理、挂路由、起后台任务。
不要在这文件里写任何业务逻辑 —— 它一变，全部接口的启动路径都跟着变。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app import __version__
from app.api.deps import get_warmup_runner
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.core.scheduler import PeriodicJob


def _start_warmup_job() -> PeriodicJob | None:
    """要不要起"主动预热"这个后台任务。

    默认**不开**（``PLOVE_WARMUP_ENABLED``）：它会在没人访问的时候也去请求源站，
    属于"默认打开会很意外"的一件事。生产环境显式打开即可。
    """
    settings = get_settings()
    if not settings.warmup_enabled:
        return None

    runner = get_warmup_runner(settings)
    return PeriodicJob(
        name="缓存预热",
        interval=settings.warmup_interval_seconds,
        work=lambda: runner.run_once(reason="定时"),
        initial_delay=settings.warmup_initial_delay,
    ).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭时要干的事。后台任务必须在这里收尾 —— 否则测试里会留下野生线程。"""
    # 启动时确保数据库引擎初始化与表列自动迁移对齐
    try:
        from app.db.session import get_engine

        get_engine()
    except Exception as db_err:
        from app.core.logging import get_logger

        get_logger("db").warning("数据库启动列对齐跳过: %s", db_err)

    job = _start_warmup_job()

    # 开机异步静默预热：延迟 3 秒避开服务初始化峰值，在后台线程自动把各源首页及前 3 分类温热落盘
    settings = get_settings()
    import threading

    def _boot_warmup():
        try:
            runner = get_warmup_runner(settings)
            runner.start_in_background(reason="开机自启静默温热")
        except Exception:
            pass

    boot_timer = threading.Timer(3.0, _boot_warmup)
    boot_timer.daemon = True
    boot_timer.start()

    try:
        yield
    finally:
        boot_timer.cancel()
        if job is not None:
            job.stop()


_PORTAL_HTML_PATH = Path(__file__).resolve().parent / "core" / "portal.html"
_PORTAL_HTML = _PORTAL_HTML_PATH.read_text(encoding="utf-8") if _PORTAL_HTML_PATH.is_file() else ""


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    #: 线上可以把 /docs 关掉（PLOVE_DOCS_ENABLED=false），一行环境变量的事。
    app = FastAPI(
        title=settings.name,
        version=__version__,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_backend_portal():
        return HTMLResponse(content=_PORTAL_HTML)

    return app


app = create_app()

