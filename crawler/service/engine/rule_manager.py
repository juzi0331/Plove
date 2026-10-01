"""规则管理器：规则持久化、Python 脚本仓库管理、热加载与缓存。"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from .models import SiteRule
from ..config import settings
from ..core.errors import CrawlerServiceError, ErrorCode
from ..core.log import get_logger

logger = get_logger("rule_manager")


class RuleManager:
    """管理站点规则与 Python 单文件采集器脚本的加载、校验、热更新。"""

    def __init__(self, rules_dir: Optional[Path] = None, sites_dir: Optional[Path] = None) -> None:
        self.rules_dir = Path(rules_dir or settings.RULES_DIR)
        self.rules_dir.mkdir(parents=True, exist_ok=True)

        # 爬虫站点仓库目录（位于 crawler/sites）
        if sites_dir:
            self.sites_dir = Path(sites_dir)
        else:
            self.sites_dir = Path(__file__).resolve().parents[2] / "sites"
        self.sites_dir.mkdir(parents=True, exist_ok=True)

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
                logger.info("已载入 JSON 站点规则: %s (%s)", rule.key, rule.name)
            except Exception as exc:
                logger.error("解析规则文件失败 %s: %s", file.name, exc)
        self._rules_cache = loaded

    def list_rules(self) -> list[SiteRule]:
        return list(self._rules_cache.values())

    def list_unified_sites(self) -> list[dict[str, Any]]:
        """获取所有站点列表（合并 JSON 规则与 Python 单文件采集器脚本）。"""
        self.reload_all()
        sites: list[dict[str, Any]] = []

        # 1. 扫描 Python 单文件采集器 (crawler/sites/*.py)
        if self.sites_dir.is_dir():
            for py_file in sorted(self.sites_dir.glob("*.py")):
                if py_file.name.startswith("__") or py_file.name.startswith("."):
                    continue
                try:
                    meta = self._inspect_script_meta(py_file)
                    sites.append({
                        "key": meta.get("key") or py_file.stem,
                        "name": meta.get("name") or py_file.stem,
                        "version": meta.get("version", "1.0.0"),
                        "base_url": meta.get("base_url", ""),
                        "mode": meta.get("mode", "direct"),
                        "data_type": "python",
                        "script_type": "standalone_python",
                        "file_path": str(py_file.name),
                        "file_size": py_file.stat().st_size,
                        "updated_at": py_file.stat().st_mtime,
                        "can_edit_code": True,
                    })
                except Exception as exc:
                    logger.warning("解析脚本元数据失败 %s: %s", py_file.name, exc)

        # 2. 加入 JSON 规则定义站点
        for rule in self._rules_cache.values():
            # 若已有同名 Python 脚本，以 Python 脚本为主，否则追加
            if not any(s["key"] == rule.key for s in sites):
                sites.append({
                    "key": rule.key,
                    "name": rule.name,
                    "version": rule.version,
                    "base_url": rule.base_url,
                    "mode": rule.mode,
                    "data_type": rule.data_type,
                    "script_type": "json_rule",
                    "file_path": f"{rule.key}.json",
                    "can_edit_code": False,
                })

        return sites

    def _inspect_script_meta(self, path: Path) -> dict[str, str]:
        """通过 AST 静态提取采集脚本中的元数据（KEY, NAME, BASE_URL 等）。"""
        meta: dict[str, str] = {
            "key": path.stem,
            "name": path.stem,
            "version": "1.0.0",
            "base_url": "",
            "mode": "direct",
        }
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                            key_name = target.id.upper()
                            if key_name in ("KEY", "NAME", "VERSION", "BASE_URL", "MODE"):
                                meta[key_name.lower()] = str(node.value.value)
        except Exception:
            pass
        return meta

    def get_script_code(self, key: str) -> str:
        """读取指定 key 的 Python 脚本源码。"""
        clean_key = re.sub(r"[^a-zA-Z0-9_]", "", key).strip()
        py_file = self.sites_dir / f"{clean_key}.py"
        if not py_file.is_file():
            raise CrawlerServiceError(ErrorCode.SITE_NOT_FOUND, f"未找到采集脚本: {clean_key}.py")
        return py_file.read_text(encoding="utf-8", errors="replace")

    def save_script(self, key: str, code: str) -> dict[str, Any]:
        """将测试通过的 Python 脚本保存落盘到 crawler/sites/<key>.py。"""
        clean_key = re.sub(r"[^a-zA-Z0-9_]", "", key).strip()
        if not clean_key:
            raise CrawlerServiceError(ErrorCode.BAD_REQUEST, "无效的站点 Key")

        # 语法合规简单探测
        try:
            ast.parse(code)
        except SyntaxError as exc:
            raise CrawlerServiceError(ErrorCode.RULE_SYNTAX_ERROR, f"Python 语法错误: {exc.msg}")

        py_file = self.sites_dir / f"{clean_key}.py"
        py_file.write_text(code, encoding="utf-8")
        logger.info("已成功将 Python 采集脚本落盘到站点库: %s.py", clean_key)
        return {
            "key": clean_key,
            "file": py_file.name,
            "size": len(code.encode("utf-8")),
            "lines": len(code.splitlines()),
        }

    def delete_script(self, key: str) -> bool:
        """从站点库中删除指定 Python 脚本。"""
        clean_key = re.sub(r"[^a-zA-Z0-9_]", "", key).strip()
        py_file = self.sites_dir / f"{clean_key}.py"
        if py_file.is_file():
            py_file.unlink()
            logger.info("已删除站点库脚本: %s.py", clean_key)
            return True
        return False

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
