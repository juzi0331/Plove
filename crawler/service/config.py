"""crawler_service 服务配置。"""

import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseModel):
    # 服务主机与端口（纯本地绑定，严禁向 0.0.0.0 开放，杜绝外部扫描与非受信访问）
    HOST: str = os.getenv("CRAWLER_SERVICE_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("CRAWLER_SERVICE_PORT", "8088"))
    
    # 日志级别
    LOG_LEVEL: str = os.getenv("CRAWLER_LOG_LEVEL", "INFO")
    
    # 规则存储目录
    RULES_DIR: Path = Path(os.getenv("CRAWLER_RULES_DIR", str(BASE_DIR / "rules")))
    
    # 抓取默认配置
    DEFAULT_TIMEOUT: float = float(os.getenv("CRAWLER_DEFAULT_TIMEOUT", "15.0"))
    DEFAULT_PLAY_TIMEOUT: float = float(os.getenv("CRAWLER_PLAY_TIMEOUT", "8.0"))
    MAX_CONCURRENCY: int = int(os.getenv("CRAWLER_MAX_CONCURRENCY", "10"))
    
    # 默认请求头
    DEFAULT_USER_AGENT: str = os.getenv(
        "CRAWLER_DEFAULT_UA",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )

settings = Settings()
