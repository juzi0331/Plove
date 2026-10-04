"""后台采集器管理契约。

包含采集器代码校验、安全沙盒检测、源码查看与热上传激活载荷。
对应契约: admin-crawler-*.json
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.site import SiteMeta


class CrawlerValidateRequest(BaseModel):
    """请求验证采集器脚本代码。"""

    code: str = Field(min_length=10, description="Python 采集器源码")
    key: str | None = Field(default=None, description="可选的站点 key（若不提供则从代码中探测）")


class CrawlerValidateResult(BaseModel):
    """采集器校验结果。"""

    valid: bool = Field(description="是否通过全部安全检查与冒烟协议测试")
    key: str = Field(description="探测到的站点 key")
    meta: SiteMeta | None = Field(default=None, description="如果协议测试通过，返回的站点元信息")
    error: str | None = Field(default=None, description="未通过时的具体错误原因")
    checks: list[str] = Field(default_factory=list, description="通过的检查项目列表")


class CrawlerUploadRequest(BaseModel):
    """上传采集器脚本。"""

    key: str = Field(pattern=r"^[a-z_][a-z0-9_]{1,63}$", description="站点 key，如 custom_site")
    code: str = Field(min_length=10, description="Python 源码")
    overwrite: bool = Field(default=False, description="若站点已存在是否允许覆盖")
    auto_bump_version: bool = Field(
        default=True,
        description="若覆盖已存在脚本且版本号未变动，是否自动自增修订号(如 1.0.0 -> 1.0.1)",
    )
    custom_version: str | None = Field(
        default=None,
        description="自定义版本号（如 1.2.0），若指定则优先使用该版本号注入/更新 meta",
    )


class CrawlerUploadResult(BaseModel):
    """上传采集器结果。"""

    success: bool = Field(description="是否成功落盘并激活")
    message: str = Field(description="提示信息")
    meta: SiteMeta = Field(description="站点元信息")


class CrawlerCodePayload(BaseModel):
    """查看采集器脚本源码。"""

    key: str = Field(description="站点 key")
    code: str = Field(description="源码内容")
    updated_at: str = Field(default="", description="文件最后修改时间")
