"""统一错误定义与错误码。"""

from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    # 网络与传输
    TIMEOUT = "TIMEOUT"
    HTTP_ERROR = "HTTP_ERROR"
    BLOCKED = "BLOCKED"  # 被源站反爬拦截 / 闸门未通过
    
    # 解析与规则
    RULE_SYNTAX_ERROR = "RULE_SYNTAX_ERROR"  # 规则格式或语法错误
    SITE_NOT_FOUND = "SITE_NOT_FOUND"        # 未找到对应站点规则
    PARSE_ERROR = "PARSE_ERROR"              # 数据解析失败 / 节点未命中
    UNSUPPORTED = "UNSUPPORTED"              # 该站点不支持该动作 (例如无 search)
    NOT_FOUND = "NOT_FOUND"                  # 404 目标影片或剧集不存在
    
    # 系统与兜底
    BAD_REQUEST = "BAD_REQUEST"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


class CrawlerServiceError(Exception):
    """统一爬虫服务异常。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_envelope_error(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }
