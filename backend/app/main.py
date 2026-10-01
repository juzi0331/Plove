"""应用组装。

这里**只做组装**：建 app、挂中间件、注册异常处理、挂路由、起后台任务。
不要在这文件里写任何业务逻辑 —— 它一变，全部接口的启动路径都跟着变。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    job = _start_warmup_job()
    try:
        yield
    finally:
        if job is not None:
            job.stop()


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

    return app


app = create_app()
