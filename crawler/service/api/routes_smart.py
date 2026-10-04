"""智能 URL 一键抓取、AI 提示词生成、脚本测试与规则固化 API。

向下兼容入口：全部路由实现已重构解耦至 .routes_smart 模块包。
"""

from .routes_smart import _build_injected_visual_proxy_html, build_injected_visual_proxy_html, router

__all__ = ["router", "_build_injected_visual_proxy_html", "build_injected_visual_proxy_html"]
