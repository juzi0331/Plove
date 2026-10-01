"""规则管理器：规则持久化、热加载与缓存。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import SiteRule
from ..config import settings
from ..core.errors import CrawlerServiceError, ErrorCode
from ..core.log import get_logger

logger = get_logger("rule_manager")


class RuleManager:
    """管理站点规则的加载、校验、热更新。"""

    def __init__(self, rules_dir: Optional[Path] = None) -> None:
        self.rules_dir = Path(rules_dir or settings.RULES_DIR)
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self._rules_cache: dict[str, SiteRule] = {}
        self.reload_all()

    def reload_all(self) -> None:
        """重新扫描并加载所有规则文件。"""
        loaded = {}
        for file in self.rules_dir.glob("*.json"):
            try:
                content = file.read_text(encoding="utf-8")
                raw = json.loads(content)
                rule = SiteRule.model_validate(raw)
                loaded[rule.key] = rule
                logger.info("已载入站点规则: %s (%s)", rule.key, rule.name)
            except Exception as exc:
                logger.error("解析规则文件失败 %s: %s", file.name, exc)
        self._rules_cache = loaded

    def list_rules(self) -> list[SiteRule]:
        return list(self._rules_cache.values())

    def get_rule(self, key: str) -> SiteRule:
        rule = self._rules_cache.get(key)
        if not rule:
            # 尝试冷加载单文件
            file = self.rules_dir / f"{key}.json"
            if file.is_file():
                try:
                    rule = SiteRule.model_validate_json(file.read_text(encoding="utf-8"))
                    self._rules_cache[key] = rule
                    return rule
                except Exception as exc:
                    raise CrawlerServiceError(
                        ErrorCode.RULE_SYNTAX_ERROR,
                        f"规则文件损坏 {key}.json: {exc}",
                    )
            raise CrawlerServiceError(ErrorCode.SITE_NOT_FOUND, f"未找到站点规则: {key}")
        return rule

    def save_rule(self, rule_data: dict) -> SiteRule:
        """校验并持久化新规则。"""
        try:
            rule = SiteRule.model_validate(rule_data)
        except Exception as exc:
            raise CrawlerServiceError(
                ErrorCode.RULE_SYNTAX_ERROR,
                f"规则定义不合法: {exc}",
            )

        file = self.rules_dir / f"{rule.key}.json"
        file.write_text(rule.model_dump_json(indent=2), encoding="utf-8")
        self._rules_cache[rule.key] = rule
        logger.info("成功落盘保存站点规则: %s", rule.key)
        return rule

    def delete_rule(self, key: str) -> bool:
        """删除指定规则。"""
        file = self.rules_dir / f"{key}.json"
        if file.is_file():
            file.unlink()
        if key in self._rules_cache:
            del self._rules_cache[key]
            logger.info("已删除站点规则: %s", key)
            return True
        return False


rule_manager = RuleManager()
