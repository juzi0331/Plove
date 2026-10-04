"""通用规则模型定义 (Pydantic)。

采用声明式结构，驱动通用抓取引擎适配任何 HTML 或 JSON 目标站。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ExtractorType(str, Enum):
    CSS = "css"              # CSS 选择器 (针对 HTML)
    JSON_PATH = "json_path"  # 点分路径或 JSONPath (针对 JSON)
    REGEX = "regex"          # 正则表达式直接提取
    CONSTANT = "constant"    # 常量固定值
    TEMPLATE = "template"    # 模板拼接，如 "{base_url}/play/{id}"


class FieldExtractor(BaseModel):
    """单字段抽取器配置。"""

    type: ExtractorType = ExtractorType.CSS
    selector: Optional[str] = None          # CSS 选择器、JSON 键路径、或正则
    attribute: Optional[str] = None         # HTML 属性名，如 "href", "src", "data-src"；None 表示取 innerText
    regex: Optional[str] = None             # 二次过滤正则，使用括号捕获，如 r"/detail/(\d+)\.html"
    regex_group: int = 1                    # 正则捕获组编号
    default: Optional[str] = ""             # 默认值
    template: Optional[str] = None          # 格式化模板，如 "第{value}集"
    strip: bool = True                      # 是否压缩首尾空白


class VodItemRule(BaseModel):
    """视频条目提取规则（归一化为 vod_id, vod_name, vod_pic, vod_remarks）。"""

    vod_id: FieldExtractor
    vod_name: FieldExtractor
    vod_pic: Optional[FieldExtractor] = None
    vod_remarks: Optional[FieldExtractor] = None


class CategoryItemRule(BaseModel):
    """分类条目提取规则。"""

    tid: FieldExtractor
    name: FieldExtractor


class EpisodeItemRule(BaseModel):
    """剧集单集提取规则。"""

    ep_index: Optional[FieldExtractor] = None
    ep_name: FieldExtractor
    play_id: FieldExtractor
    line: Optional[FieldExtractor] = None


class LineItemRule(BaseModel):
    """播放线路提取规则。"""

    line: FieldExtractor
    name: FieldExtractor


# ------------------------------------------------------------- 各动作规则定义

class HomeRule(BaseModel):
    """首页动作规则。"""

    path: str = "/"
    method: str = "GET"
    # 分类提取
    categories_container: Optional[str] = None
    category_item: Optional[CategoryItemRule] = None
    static_categories: Optional[list[dict[str, str]]] = None  # 静态预设分类兜底

    # 推荐列表提取
    recommend_container: Optional[str] = None
    recommend_item: Optional[VodItemRule] = None


class CategoryRule(BaseModel):
    """分类列表动作规则。"""

    path: str  # 支持占位符: {tid}, {page}
    method: str = "GET"
    list_container: str
    item: VodItemRule
    # 分页判定
    has_more_extractor: Optional[FieldExtractor] = None
    page_size: int = 20


class DetailRule(BaseModel):
    """影片详情动作规则。"""

    path: str  # 支持占位符: {id}
    method: str = "GET"
    
    # 基本信息
    title_extractor: FieldExtractor
    pic_extractor: Optional[FieldExtractor] = None
    desc_extractor: Optional[FieldExtractor] = None
    remarks_extractor: Optional[FieldExtractor] = None

    # 剧集与线路
    episodes_container: str
    episode_item: EpisodeItemRule
    lines_container: Optional[str] = None
    line_item: Optional[LineItemRule] = None


class PlayRule(BaseModel):
    """播放嗅探动作规则。"""

    path: str  # 支持占位符: {id}, {ep}, {play_id}, {line}
    method: str = "GET"
    # 播放地址抽取 (通常为 m3u8 正则或特定字段)
    play_url_extractor: FieldExtractor
    format: str = "m3u8"
    headers: Optional[dict[str, str]] = None  # 防盗链头


class SearchRule(BaseModel):
    """搜索动作规则。"""

    path: str  # 支持占位符: {kw}, {page}
    method: str = "GET"
    list_container: str
    item: VodItemRule
    has_more_extractor: Optional[FieldExtractor] = None


class SiteRule(BaseModel):
    """完整站点通用采集规则定义。"""

    key: str = Field(..., pattern=r"^[a-zA-Z0-9_]{1,64}$", description="站点唯一标识，如 ai2048, ncat21")
    name: str = Field(..., description="站点展示名称")
    version: str = Field("1.0.0", description="规则版本号")
    base_url: str = Field(..., description="目标站点基础 URL，如 https://example.com")
    mode: str = Field("direct", description="播放代理模式: direct | proxy")
    data_type: str = Field("html", description="目标数据类型: html | json")
    encoding: Optional[str] = Field("utf-8", description="页面文本编码")
    custom_headers: Optional[dict[str, str]] = Field(default_factory=dict, description="自定义请求头")
    ad_patterns: Optional[list[str]] = Field(default_factory=list, description="去广告正则列表")

    # 动作映射
    home: Optional[HomeRule] = None
    category: Optional[CategoryRule] = None
    detail: Optional[DetailRule] = None
    play: Optional[PlayRule] = None
    search: Optional[SearchRule] = None
