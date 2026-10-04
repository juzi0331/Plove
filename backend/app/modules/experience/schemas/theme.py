"""体验层主题配置与 Token Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BrandConfig(BaseModel):
    """品牌与标识配置。"""

    name: str = Field(default="Plove", description="站点或品牌展示名称")
    logo_url: str = Field(default="", description="品牌 Logo 图标地址（空则显示文字）")


class ColorTokens(BaseModel):
    """色彩设计 Token。"""

    background: str = Field(default="#141414", description="页面主背景色")
    surface: str = Field(default="#202020", description="卡片与容器表面背景色")
    primary: str = Field(default="#E50914", description="品牌主色调（按钮/高亮/进度条）")
    text: str = Field(default="#FFFFFF", description="主要文字颜色")
    muted: str = Field(default="#B8B8B8", description="次要弱化文字颜色")
    border: str = Field(default="#2A2A2A", description="边框与分割线颜色")
    danger: str = Field(default="#E50914", description="警告或危险颜色")


class TypographyTokens(BaseModel):
    """排版设计 Token。"""

    family: str = Field(default="system", description="字体族预设: system / inter / roboto")
    body_px: int = Field(default=15, ge=12, le=24, description="正文字号像素 (12-24)")
    title_px: int = Field(default=26, ge=18, le=48, description="标题字号像素 (18-48)")


class LayoutTokens(BaseModel):
    """页面布局与间距 Token。"""

    max_width_px: int = Field(default=1440, ge=960, le=2560, description="页面最大宽度像素")
    page_padding_px: int = Field(default=16, ge=0, le=64, description="页面边缘内边距像素")
    gap_px: int = Field(default=14, ge=0, le=48, description="栅格与板块间距像素")


class CardTokens(BaseModel):
    """海报卡片设计 Token。"""

    aspect_ratio: str = Field(default="16:9", description="卡片海报比例 (16:9, 2:3, 3:4, 1:1)")
    radius_px: int = Field(default=6, ge=0, le=32, description="卡片圆角半径像素 (0-32)")
    image_fit: str = Field(default="cover", description="图片填充模式: cover / contain")


class MotionTokens(BaseModel):
    """动态效果与过渡 Token。"""

    preset: str = Field(default="subtle", description="动效预设: none / subtle / smooth")
    duration_ms: int = Field(default=200, ge=0, le=1000, description="交互过渡基础毫秒数")


class PlayerDefaults(BaseModel):
    """播放器客户端全局默认偏好。"""

    auto_next: bool = Field(default=True, description="播放完毕后是否自动播放下一集")
    auto_next_delay_seconds: int = Field(default=5, ge=1, le=30, description="连播倒计时秒数")
    default_rate: float = Field(default=1.0, ge=0.5, le=3.0, description="默认播放倍速")
    allowed_rates: list[float] = Field(
        default_factory=lambda: [0.75, 1.0, 1.25, 1.5, 2.0],
        description="可选播放倍速列表",
    )
    hud_hide_after_ms: int = Field(default=3500, ge=1000, le=10000, description="播放控制栏自动淡出隐藏毫秒数")


class ThemeConfig(BaseModel):
    """完整主题配置。"""

    color: ColorTokens = Field(default_factory=ColorTokens, description="色彩方案")
    typography: TypographyTokens = Field(default_factory=TypographyTokens, description="字体排版")
    layout: LayoutTokens = Field(default_factory=LayoutTokens, description="布局间距")
    card: CardTokens = Field(default_factory=CardTokens, description="卡片形态")
    motion: MotionTokens = Field(default_factory=MotionTokens, description="动效与交互")
