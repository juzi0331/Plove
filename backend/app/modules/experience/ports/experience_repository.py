"""体验层持久化仓储协议 (Port)。"""

from __future__ import annotations

from typing import Protocol

from app.models.experience import ExperienceActivePointer, ExperienceDraft, ExperienceRelease


class ExperienceRepositoryProtocol(Protocol):
    """前台体验仓储抽象接口。"""

    def get_or_create_draft(self, draft_id: str = "default") -> ExperienceDraft:
        """获取指定草稿，若不存在则创建内置默认草稿。"""
        ...

    def save_draft(
        self,
        draft_id: str,
        current_revision: int,
        brand_json: str,
        theme_json: str,
        navigation_json: str,
        pages_json: str,
        player_defaults_json: str,
        updated_by: str = "admin",
    ) -> ExperienceDraft:
        """乐观并发更新草稿，若当前 revision 不匹配抛出并发冲突。"""
        ...

    def get_active_release(
        self, channel: str = "default"
    ) -> tuple[ExperienceRelease | None, ExperienceActivePointer | None]:
        """获取当前指定渠道生效的发布快照与指针。"""
        ...

    def get_release(self, release_id: str) -> ExperienceRelease | None:
        """通过 release_id 获取指定的历史不可变快照。"""
        ...

    def list_releases(self, limit: int = 50) -> list[ExperienceRelease]:
        """获取最近发布记录列表。"""
        ...

    def create_release_and_activate(
        self,
        release_id: str,
        brand_json: str,
        theme_json: str,
        navigation_json: str,
        pages_json: str,
        player_defaults_json: str,
        published_by: str = "admin",
        note: str = "",
        channel: str = "default",
    ) -> tuple[ExperienceRelease, ExperienceActivePointer]:
        """在单事务中原子创建新发布快照并推进激活指针。"""
        ...
