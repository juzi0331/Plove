"""配置：全部来自带 ``PLOVE_`` 前缀的环境变量（可写进 ``.env``）。

刻意不做的事：不在这里读数据库、不在这里做校验以外的副作用。
配置就是配置，读不到就用默认值，读不懂就在启动时炸掉。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: 后端根目录 ``backend/`` —— 本文件在 ``backend/app/core/config.py``
BACKEND_DIR = Path(__file__).resolve().parents[2]
#: 仓库根（``backend/`` 的上一层），爬虫与契约都挂在这里
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """运行配置。字段名 = 环境变量去掉 ``PLOVE_`` 前缀。"""

    model_config = SettingsConfigDict(
        env_prefix="PLOVE_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = "Plove API"
    env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 4001
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    #: 是否开 ``/docs``（Swagger）与 ``/openapi.json``。
    #: 开发时开着最方便；上线后要不要关是你的选择 ——
    #: 它不泄露密码，但会把全部接口形状公开（包括后台接口的路径）。
    #: 关掉只需一行环境变量，比"改代码重新部署"轻。
    docs_enabled: bool = True

    #: 爬虫目录（默认仓库根下的 ``crawler/``）
    crawler_dir: Path = PROJECT_DIR / "crawler"
    #: 爬虫单次调用超时（秒）。到点直接 kill 子进程，不拖慢在线服务。
    #: 爬虫自己永远不超时（它不知道调用方的耐心），超时是**我们**的责任。
    #:
    #: 取值依据是**实测，而且是反复实测**（同一台机器、同一天不同时刻）：
    #:
    #: ===================  ==============  =============
    #: 命令                 ai2048          ncat21
    #: ===================  ==============  =============
    #: home                 2.0s            5.2s ~ **8.9s**
    #: detail               1.0s            2.9s ~ **5.9s**
    #: play（不带 play_id）  1.0s ~ 1.2s     4.1s ~ **7.2s**
    #: play（带 play_id）   —               ~ **4.0s**
    #: ===================  ==============  =============
    #:
    #: ncat21 慢是它自己造成的（它带 1 秒主动限速，一个页面要 2~3 次请求），
    #: 而且波动很大 —— 早先按 4s 量出来配的 10 秒超时，后来真真切切地
    #: 超时过一次。所以留到 2 倍以上。
    #:
    #: **不要凭感觉调小。** 5s 那种值会变成"平时刚好、网络一抖就 504"，
    #: 而用户看到的是"这个站彻底坏了"。代价只是极端情况下多占一会儿线程，
    #: 而线程数本来就受并发上限约束（最多 ``global_max_concurrency`` 个）。
    crawler_timeout: float = 20.0
    #: 播放类命令另算（带 play_id 后实测约 4s，不带约 7.2s，再留一倍余量）
    crawler_timeout_play: float = 25.0
    #: 契约目录（后端下的 ``contracts/``）
    contracts_dir: Path = BACKEND_DIR / "contracts"

    # -------------------------------------------------------------- 缓存
    #: 目录类内容的缓存生存时间（秒）。**设成 0 就等于关掉这一类缓存。**
    #:
    #: 取值依据是"这东西多久会变"，不是"能省多少"：源站目录一天最多更新几次，
    #: 而每抓一次都要 fork 一个子进程、花 1~4 秒。
    #: 播放地址**永远不缓存**（m3u8 带时效签名），所以这里没有它。
    cache_ttl_home: float = 600.0
    cache_ttl_category: float = 300.0
    cache_ttl_detail: float = 300.0
    #: 缓存条数上限（LRU 淘汰）。一条首页负载约几十 KB，512 条量级在 10MB 内。
    cache_maxsize: int = 512

    # -------------------------------------------------------------- 稳定性
    #: 单个源允许同时在跑的爬虫子进程数。
    #: 别调大：真正在保护的是那台 10Mbps 的 VPS 和源站的耐心。
    site_max_concurrency: int = 2
    #: **全站**同时在跑的爬虫子进程数上限。默认 4 = 现在 2 个源 × 每站 2。
    #:
    #: 为什么要单独有一个：只有"每站上限"的话，源变多之后总数是**乘出来**的 ——
    #: 10 个源 × 2 = 20 个并发子进程，内存和 CPU 一起完蛋。
    #: 每站上限保护源站，全站上限保护这台机器。
    global_max_concurrency: int = 4
    #: 抢不到并发槽位时最多排多久（秒）。到点明确回 ``UPSTREAM_BUSY`` ——
    #: 让请求快速失败，比让它无限等待好（等待会连着占住连接和线程）。
    site_queue_timeout: float = 20.0
    #: 连续失败多少次就熔断该源。注意只有"源站故障类"错误计入，
    #: ``NOT_FOUND`` / ``UNSUPPORTED`` 这类**正确的回答**不算（见 crawler/guard.py）。
    breaker_fail_threshold: int = 5
    #: 熔断后冷却多久（秒），冷却结束放**一个**探针试探。
    breaker_reset_seconds: float = 60.0

    # -------------------------------------------------------------- 主动预热
    #: 是否开启"定时主动抓取入口页填进缓存"。
    #:
    #: **默认关**：它会在没人访问的时候也去请求源站，属于"默认开启会很意外"
    #: 的一件事。生产环境请显式打开（见 .env.example）。
    #:
    #: 它解决的是 TTL 的一个固有毛病：TTL 到点后是**下一个来访者**触发重抓、
    #: 由**他**承担 1~5 秒的等待，而且没人来的话数据会一直旧着。
    #: 主动预热让用户永远命中新鲜数据、也永远不用等，顺带把"重启后缓存全空"
    #: 的冷启动也填上了。
    warmup_enabled: bool = False
    #: 预热周期（秒）。86400 = 24 小时。
    #: 建议把它设成**比 TTL 略短**（比如 TTL 25 小时 / 周期 24 小时），
    #: 这样缓存永远不会因为自然过期而被普通请求重新触发。
    warmup_interval_seconds: float = 86400.0
    #: 启动后等多久才开始第一次预热（秒）。别和启动时的第一批请求抢源站。
    warmup_initial_delay: float = 60.0
    #: 每个源预热几个分类的第一页。
    #: **不要调很大**：详情页不预热（有无穷多），分类也只需热入口那几个。
    #: 全热 = 定时自己去爬整个站，那是主动给源站压力。
    warmup_max_categories: int = 3

    #: 数据库连接串。
    #:
    #: 默认值是**本地 SQLite 文件**，仅为让本地 clone 下来就能直接跑测试；
    #: 真实环境（宝塔 / NAS 上的 MySQL）**必须**用 ``.env`` 覆盖它，例如::
    #:
    #:     PLOVE_DATABASE_URL=mysql+pymysql://plove:密码@192.168.1.10:3306/plove?charset=utf8mb4
    #:
    #: 表结构只用可移植类型（见 ``app/db/__init__.py`` 的规矩），
    #: 所以同一套模型两种库都能跑，不会出现"本地绿、线上炸"。
    database_url: str = f"sqlite+pysqlite:///{(BACKEND_DIR / 'plove-dev.db').as_posix()}"
    database_echo: bool = False

    #: 心跳间隔（秒），由服务端下发给客户端，客户端照着这个频率来
    heartbeat_interval_seconds: int = 30

    #: 后台管理接口令牌，尚未启用
    admin_token: str = ""

    @field_validator("crawler_dir", mode="before")
    @classmethod
    def _blank_crawler_dir_uses_default(cls, value: object) -> object:
        """.env 留空时使用仓库默认 crawler/，避免 Path('') 落到当前目录。"""
        if value is None or (isinstance(value, str) and not value.strip()):
            return PROJECT_DIR / "crawler"
        return value

    @field_validator("contracts_dir", mode="before")
    @classmethod
    def _blank_contracts_dir_uses_default(cls, value: object) -> object:
        """.env 留空时使用 backend/contracts/。"""
        if value is None or (isinstance(value, str) and not value.strip()):
            return BACKEND_DIR / "contracts"
        return value

    @property
    def is_dev(self) -> bool:
        return self.env.lower() in ("dev", "local", "test")

    @property
    def sites_dir(self) -> Path:
        return self.crawler_dir / "sites"

    @property
    def schemas_dir(self) -> Path:
        return self.contracts_dir / "schemas"


@lru_cache
def get_settings() -> Settings:
    """进程内单例。测试里要换配置就 ``get_settings.cache_clear()``。"""
    return Settings()
