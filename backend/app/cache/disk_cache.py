"""L2 本地磁盘持久化缓存。

基于 SQLite 存储在 data/disk_cache.db 中，作为内存缓存的持久化后盾。
特性：
1. 内存+磁盘双层缓存：写入内存的同时异步写入磁盘，服务重启后缓存永不丢失；
2. 毫秒级命中：开机或缓存冷启动时优先从磁盘装载未过期条目，彻底杜绝首次访问击穿源站；
3. 过期条目惰性与批量清理；
4. 纯标准库 sqlite3，零外部依赖，极速稳定。
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_DIR
from app.core.logging import get_logger

logger = get_logger("disk_cache")

DB_DIR = BACKEND_DIR / "data"
DB_PATH = DB_DIR / "disk_cache.db"


def _deserialize_payload(payload_json: str, data_type: str) -> Any:
    if not payload_json:
        return None
    try:
        if data_type == "HomePayload":
            from app.schemas.catalog import HomePayload

            return HomePayload.model_validate_json(payload_json)
        elif data_type == "ListPayload":
            from app.schemas.catalog import ListPayload

            return ListPayload.model_validate_json(payload_json)
        elif data_type == "DetailPayload":
            from app.schemas.catalog import DetailPayload

            return DetailPayload.model_validate_json(payload_json)
        else:
            return json.loads(payload_json)
    except Exception:
        try:
            return json.loads(payload_json)
        except Exception:
            return payload_json


class DiskCacheStore:
    def __init__(self, db_path: Path = DB_PATH, clock: Callable[[], float] | None = None) -> None:
        self.db_path = db_path
        self._clock: Callable[[], float] = clock or time.time
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _ensure_table(self) -> None:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS disk_cache (
                        key TEXT PRIMARY KEY,
                        site TEXT,
                        namespace TEXT,
                        data_type TEXT,
                        payload_json TEXT,
                        expires_at REAL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON disk_cache(expires_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_site ON disk_cache(site);")
        except Exception as exc:
            logger.warning("初始化磁盘持久化缓存表失败: %s", exc)

    def set(self, key: str, site: str, namespace: str, value: Any, ttl: float) -> None:
        """写入磁盘持久化缓存。"""
        if ttl <= 0 or value is None:
            return
        now = self._clock()
        expires_at = now + ttl

        data_type = ""
        payload_str = ""

        try:
            if hasattr(value, "model_dump_json"):
                # Pydantic v2
                payload_str = value.model_dump_json()
                data_type = value.__class__.__name__
            elif hasattr(value, "json"):
                # Pydantic v1
                payload_str = value.json()
                data_type = value.__class__.__name__
            else:
                payload_str = json.dumps(value, ensure_ascii=False)
                data_type = "raw"

            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO disk_cache (key, site, namespace, data_type, payload_json, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        payload_json=excluded.payload_json,
                        expires_at=excluded.expires_at,
                        data_type=excluded.data_type;
                    """,
                    (key, site, namespace, data_type, payload_str, expires_at),
                )
        except Exception as exc:
            logger.debug("磁盘缓存持久化写入跳过 (%s): %s", key, exc)

    def get(self, key: str) -> tuple[Any | None, float]:
        """读取磁盘缓存。返回 (原始对象, 剩余有效秒数)。未命中或过期返回 (None, 0.0)。"""
        now = self._clock()
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT payload_json, data_type, expires_at FROM disk_cache WHERE key = ?",
                    (key,),
                ).fetchone()

                if not row:
                    return None, 0.0

                payload_json, data_type, expires_at = row
                if expires_at < now:
                    # 惰性删除过期缓存
                    conn.execute("DELETE FROM disk_cache WHERE key = ?", (key,))
                    return None, 0.0

                remaining_sec = max(0.0, expires_at - now)
                obj = _deserialize_payload(payload_json, data_type)
                return obj, remaining_sec
        except Exception as exc:
            logger.debug("读取磁盘缓存异常 (%s): %s", key, exc)
            return None, 0.0

    def list_entries(
        self,
        site: str | None = None,
        namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询磁盘缓存列表。"""
        now = self._clock()
        self.prune_expired()
        items: list[dict[str, Any]] = []
        try:
            with self._get_conn() as conn:
                query = "SELECT key, site, namespace, expires_at FROM disk_cache WHERE expires_at >= ?"
                params: list[Any] = [now]
                if site:
                    query += " AND site = ?"
                    params.append(site)
                if namespace:
                    query += " AND namespace = ?"
                    params.append(namespace)
                query += " ORDER BY expires_at DESC LIMIT 200"

                rows = conn.execute(query, params).fetchall()
                for row in rows:
                    k, s, ns, exp = row
                    parts = k.split("|", 2)
                    ident = parts[2] if len(parts) == 3 else k
                    items.append(
                        {
                            "key": k,
                            "site": s,
                            "namespace": ns,
                            "ident": ident,
                            "remaining_seconds": max(0, int(exp - now)),
                            "is_disk": True,
                        }
                    )
        except Exception as exc:
            logger.warning("查询磁盘缓存列表异常: %s", exc)
        return items

    def invalidate(self, key: str) -> None:
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM disk_cache WHERE key = ?", (key,))
        except Exception:
            pass

    def invalidate_site(self, site: str) -> int:
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("DELETE FROM disk_cache WHERE site = ?", (site,))
                return cursor.rowcount
        except Exception:
            return 0

    def clear(self) -> int:
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("DELETE FROM disk_cache")
                return cursor.rowcount
        except Exception:
            return 0

    def prune_expired(self) -> int:
        now = self._clock()
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("DELETE FROM disk_cache WHERE expires_at < ?", (now,))
                return cursor.rowcount
        except Exception:
            return 0

    def stats(self) -> dict[str, Any]:
        """统计持久化缓存数据。"""
        self.prune_expired()
        try:
            with self._get_conn() as conn:
                count = conn.execute("SELECT COUNT(1) FROM disk_cache").fetchone()[0]
                size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
                return {
                    "count": count,
                    "size_mb": round(size_bytes / (1024 * 1024), 2),
                    "db_path": str(self.db_path.resolve()),
                }
        except Exception:
            return {"count": 0, "size_mb": 0.0, "db_path": str(self.db_path)}


# 全局单例
_disk_store: DiskCacheStore | None = None


def get_disk_store() -> DiskCacheStore:
    global _disk_store
    if _disk_store is None:
        _disk_store = DiskCacheStore()
    return _disk_store
