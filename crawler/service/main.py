"""crawler_service 主入口（FastAPI 微服务）。"""

import sys
from pathlib import Path

_crawler_root = Path(__file__).resolve().parent.parent
if str(_crawler_root) not in sys.path:
    sys.path.insert(0, str(_crawler_root))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes_proxy import router as proxy_router
from .api.routes_rules import router as rules_router
from .api.routes_scrape import router as scrape_router
from .api.routes_smart import router as smart_router
from .api.routes_system import router as system_router
from .api.routes_tasks import router as tasks_router
from .config import settings
from .core.errors import CrawlerServiceError, ErrorCode
from .core.log import get_logger
from .engine.rule_manager import rule_manager

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Universal Crawler Service 正在启动...")
    rule_manager.reload_all()
    logger.info("已完成规则库装载，就绪提供采集服务。")
    yield
    logger.info("Universal Crawler Service 正在关闭...")


tags_metadata = [
    {
        "name": "智能采集与脚本工坊",
        "description": "输入主页 URL 智能自适应分析、针对难搞站点的 AI Prompt 提示词自动生成、外部 AI 脚本全链路安全与功能测试、一键热部署上传到 Plove 后端。",
    },
    {
        "name": "scrape",
        "description": "统一数据采集接口：调用已注册站点的 home (首页)、category (分类)、detail (详情)、play (播放流嗅探)、search (搜索)。",
    },
    {
        "name": "rules",
        "description": "站点通用规则管理：JSON 声明式规则的查看、编辑、在线计算测试与落盘存储。",
    },
    {
        "name": "tasks",
        "description": "后台全量并发抓取任务调度与状态查询。",
    },
]

app = FastAPI(
    title="Plove 通用爬虫与规则微服务 API",
    description="""
### Plove Universal Spider Service · 智能通用采集微服务

- **全自动化**：输入任意站点主页 URL，全自动探测分类、片单与播放流，并合成符合 Plove 契约的单文件 Python 爬虫脚本。
- **AI 协作闭环**：遇到高难度站点时，一键生成交付给 ChatGPT/Claude/DeepSeek 的专业提示词，AI 写完后可导入本系统进行隔离全链路测试。
- **一键热部署**：测试通过后，一键直连 Plove 后端 `/api/v1/admin/crawlers/upload`，立即热上线新源！
""",
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)


# 跨域配置：仅限本地开发与管理工作台访问
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常捕获，输出统一信封
@app.exception_handler(CrawlerServiceError)
async def handle_crawler_service_error(request: Request, exc: CrawlerServiceError):
    return JSONResponse(
        status_code=200,  # 统一协议：信封内承载错误，状态码保持 200
        content={
            "ok": False,
            "data": None,
            "error": exc.to_envelope_error(),
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("服务处理发生未捕获异常: %s", exc)
    return JSONResponse(
        status_code=200,
        content={
            "ok": False,
            "data": None,
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": f"采集服务内部错误: {exc}",
            },
        },
    )


from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_INDEX = STATIC_DIR / "index.html"

# 挂载路由
app.include_router(system_router)
app.include_router(rules_router)
app.include_router(scrape_router)
app.include_router(smart_router)
app.include_router(tasks_router)
app.include_router(proxy_router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    if STATIC_INDEX.is_file():
        return HTMLResponse(content=STATIC_INDEX.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Spider Console Not Found</h1>", status_code=404)



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "crawler.service.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
