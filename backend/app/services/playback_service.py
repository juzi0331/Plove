"""前台播放心跳与观看历史服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models.device import Device
from app.models.playback import PlaybackRecord
from app.schemas.playback import PlaybackHeartbeatRequest, PlaybackHeartbeatResult


def record_playback_heartbeat(
    session: Session,
    device: Device,
    payload: PlaybackHeartbeatRequest,
) -> PlaybackHeartbeatResult:
    """记录播放心跳，刷新设备在线/播放状态并持久化观看历史。"""
    now = utcnow()
    device.last_seen_at = now
    device.is_playing = payload.is_playing
    vod_title = payload.vod_name.strip()
    if payload.ep_name.strip():
        vod_title = f"{vod_title} · {payload.ep_name.strip()}"
    device.current_vod_title = vod_title[:255]

    if payload.is_playing:
        device.last_playback_at = now

    site_key = (payload.site or "").strip()[:64]
    # 查找此设备在此站点对此影片的历史记录（防跨站冲突：1设备1站点1影片1条记录）
    stmt = (
        select(PlaybackRecord)
        .where(
            PlaybackRecord.device_id == device.id,
            PlaybackRecord.site_key == site_key,
            PlaybackRecord.vod_id == payload.vod_id,
        )
        .limit(1)
    )
    record = session.scalar(stmt)
    if record is None:
        record = PlaybackRecord(
            device_id=device.id,
            activation_id=device.activation_id,
            vod_id=payload.vod_id,
            vod_name=payload.vod_name[:255] if payload.vod_name else "未命名影片",
            vod_pic=payload.vod_pic[:512] if payload.vod_pic else "",
            ep_name=payload.ep_name[:120] if payload.ep_name else "",
            site_key=payload.site[:64] if payload.site else "",
            position=max(0.0, float(payload.position or 0.0)),
            duration=max(0.0, float(payload.duration or 0.0)),
            progress_percent=min(100, max(0, int(payload.progress or 0))),
            is_playing=payload.is_playing,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
    else:
        if payload.vod_name:
            record.vod_name = payload.vod_name[:255]
        if payload.vod_pic:
            record.vod_pic = payload.vod_pic[:512]
        if payload.ep_name:
            record.ep_name = payload.ep_name[:120]
        if payload.site:
            record.site_key = payload.site[:64]
        record.position = max(0.0, float(payload.position or 0.0))
        record.duration = max(0.0, float(payload.duration or 0.0))
        record.progress_percent = min(100, max(0, int(payload.progress or 0)))
        record.is_playing = payload.is_playing
        record.updated_at = now

    session.flush()
    return PlaybackHeartbeatResult(ok=True, message="心跳与观看记录已更新")
