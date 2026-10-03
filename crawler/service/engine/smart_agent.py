"""智能自适应采集器（Smart Auto-Discovery Scraper）。

向下兼容入口：全部模块实现已重构解耦至 .smart_agent 模块包。
"""

from .smart_agent import SmartAgent, SmartExploreResult, StructureInspectionResult

__all__ = ["SmartAgent", "SmartExploreResult", "StructureInspectionResult"]
