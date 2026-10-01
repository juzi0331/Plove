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


from fastapi.responses import HTMLResponse

_PORTAL_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Plove Backend Service · 后端服务中枢 :4001</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #f8fafc;
      --bg-surface: #ffffff;
      --border-subtle: #e2e8f0;
      --accent-primary: #4f46e5;
      --accent-emerald: #059669;
      --accent-cyan: #0284c7;
      --text-main: #0f172a;
      --text-muted: #475569;
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', Consolas, Monaco, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg-base);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      background-image: 
        radial-gradient(at 15% 15%, rgba(79, 70, 229, 0.06) 0px, transparent 40%),
        radial-gradient(at 85% 85%, rgba(2, 132, 199, 0.06) 0px, transparent 40%);
    }
    .portal-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 20px;
      padding: 2.5rem;
      max-width: 860px;
      width: 100%;
      box-shadow: 0 16px 36px -4px rgba(15, 23, 42, 0.08);
    }
    .head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--border-subtle);
      padding-bottom: 1.5rem;
      margin-bottom: 1.75rem;
    }
    .brand-wrap {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .brand-logo {
      width: 48px;
      height: 48px;
      border-radius: 14px;
      background: linear-gradient(135deg, #4f46e5 0%, #0284c7 100%);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 1.25rem;
      box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 700;
      background: #ecfdf5;
      color: #065f46;
      border: 1px solid #a7f3d0;
    }
    .pulse {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 1.25rem;
      margin-top: 1.5rem;
    }
    .card {
      border: 1px solid var(--border-subtle);
      border-radius: 14px;
      padding: 1.25rem 1.5rem;
      background: #ffffff;
      text-decoration: none;
      color: inherit;
      transition: all 0.2s ease;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .card:hover {
      border-color: var(--accent-primary);
      box-shadow: 0 8px 20px -2px rgba(79, 70, 229, 0.1);
      transform: translateY(-2px);
    }
    .card-title {
      font-size: 1.05rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: var(--text-main);
    }
    .card-desc {
      font-size: 0.84rem;
      color: var(--text-muted);
      margin: 8px 0 12px;
      line-height: 1.5;
    }
    .card-link {
      font-size: 0.8rem;
      font-family: var(--font-mono);
      font-weight: 600;
      color: var(--accent-primary);
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .info-bar {
      margin-top: 2rem;
      padding: 1rem 1.25rem;
      border-radius: 10px;
      background: #f8fafc;
      border: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.8rem;
      color: var(--text-muted);
      font-family: var(--font-mono);
    }
  </style>
</head>
<body>
  <div class="portal-card">
    <div class="head">
      <div class="brand-wrap">
        <div class="brand-logo">PV</div>
        <div>
          <h1 style="font-size:1.35rem;font-weight:800;color:var(--text-main)">Plove Backend Service</h1>
          <p style="font-size:0.82rem;color:var(--text-muted);margin-top:2px">高性能影视聚合中枢服务端 · 端口 :4001</p>
        </div>
      </div>
      <div class="status-badge">
        <span class="pulse"></span>
        服务端正常就绪
      </div>
    </div>

    <p style="color:var(--text-muted);font-size:0.9rem;line-height:1.6">
      后端微服务正以 <code>0.0.0.0:4001</code> 全网卡模式稳定运行中。前端应用与本地爬虫均已完成与后端的通道对接。您可通过下方导航卡片直达各个管理与调试终端：
    </p>

    <div class="grid">
      <a href="/docs" class="card">
        <div>
          <div class="card-title">
            <span>在线 API 交互文档</span>
            <span style="font-size:0.75rem;color:var(--accent-primary)">Swagger UI</span>
          </div>
          <div class="card-desc">直连查看并在线调试全部 4001 接口：影视抓取、分类推荐、流地址穿透与鉴权管理。</div>
        </div>
        <div class="card-link">打开 :4001/docs &rarr;</div>
      </a>

      <a href="http://127.0.0.1:4000/_manage/sites" target="_blank" class="card">
        <div>
          <div class="card-title">
            <span>影视源与系统管理后台</span>
            <span style="font-size:0.75rem;color:var(--accent-cyan)">Vite Admin</span>
          </div>
          <div class="card-desc">前端应用内嵌的管理后台：查看各影视站健康状态、热重载配置、手动触发预热与监控。</div>
        </div>
        <div class="card-link">前往 :4000/_manage/sites &rarr;</div>
      </a>

      <a href="http://127.0.0.1:8088/" target="_blank" class="card">
        <div>
          <div class="card-title">
            <span>智能爬虫规则控制台</span>
            <span style="font-size:0.75rem;color:var(--accent-emerald)">Spider Studio</span>
          </div>
          <div class="card-desc">本地纯隔离爬虫系统：目标站点智能探测、全链路自动化体检、本地网络代理与一键热部署。</div>
        </div>
        <div class="card-link">前往 :8088 &rarr;</div>
      </a>

      <a href="http://127.0.0.1:4000/" target="_blank" class="card">
        <div>
          <div class="card-title">
            <span>前端影视播放门户</span>
            <span style="font-size:0.75rem;color:#d97706)">Client Portal</span>
          </div>
          <div class="card-desc">面向终端用户的播放与浏览前端：响应式影视推荐、多线路智能切换与 HLS 直播试播。</div>
        </div>
        <div class="card-link">前往 :4000 &rarr;</div>
      </a>
    </div>

    <div class="info-bar">
      <span>API PREFIX: /api/v1</span>
      <span>CORS: ENABLED</span>
      <span>AUTH HEADER: X-Admin-Token</span>
    </div>
  </div>
</body>
</html>
"""


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

