"""Storage retention management and automated disk cleanup."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AnalysisJob, DetectionEvent, VideoAsset

logger = logging.getLogger("lineguard.cleanup")


def cleanup_expired_storage(db: Session, max_age_days: int = 30) -> dict[str, Any]:
    """Purge old uploaded raw videos from completed jobs and expired resolved evidence to free disk space."""
    if max_age_days <= 0:
        return {"freed_bytes": 0, "freed_mb": 0.0, "videos_removed": 0, "evidence_removed": 0, "skipped": True}

    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    freed_bytes = 0
    videos_removed = 0
    evidence_removed = 0

    # 1. Clean up old videos of completed or failed analysis jobs
    completed_jobs = list(db.scalars(
        select(AnalysisJob).where(
            AnalysisJob.status.in_(["completed", "failed"]),
            AnalysisJob.completed_at.is_not(None),
            AnalysisJob.completed_at < cutoff,
        )
    ).all())

    for job in completed_jobs:
        video = db.get(VideoAsset, job.video_id)
        if video and video.storage_key:
            video_file = settings.storage_root / video.storage_key
            if video_file.exists() and video_file.is_file():
                try:
                    size = video_file.stat().st_size
                    video_file.unlink()
                    freed_bytes += size
                    videos_removed += 1
                    logger.info("Deleted expired video asset %s (%d bytes)", video.id, size)
                except Exception as exc:
                    logger.warning("Could not delete video file %s: %s", video_file, exc)

    # 2. Clean up old resolved or false-positive evidence frames
    stale_events = list(db.scalars(
        select(DetectionEvent).where(
            DetectionEvent.status.in_(["resolved", "false_positive"]),
            DetectionEvent.created_at < cutoff,
            DetectionEvent.evidence_key.is_not(None),
        )
    ).all())

    for event in stale_events:
        if event.evidence_key:
            evidence_file = settings.storage_root / event.evidence_key
            if evidence_file.exists() and evidence_file.is_file():
                try:
                    size = evidence_file.stat().st_size
                    evidence_file.unlink()
                    freed_bytes += size
                    evidence_removed += 1
                    logger.info("Deleted expired evidence file %s (%d bytes)", event.id, size)
                except Exception as exc:
                    logger.warning("Could not delete evidence file %s: %s", evidence_file, exc)

    # 3. Clean temporary live cache frames older than 1 hour
    cache_dir = settings.storage_root / "cache"
    if cache_dir.exists():
        hour_ago = datetime.now(timezone.utc).timestamp() - 3600
        for tmp_file in cache_dir.glob("*.jpg"):
            try:
                if tmp_file.stat().st_mtime < hour_ago:
                    freed_bytes += tmp_file.stat().st_size
                    tmp_file.unlink()
            except Exception:
                pass

    freed_mb = round(freed_bytes / (1024 * 1024), 2)
    logger.info("Storage cleanup finished: %d videos, %d evidence frames, freed %s MB", videos_removed, evidence_removed, freed_mb)
    return {
        "freed_bytes": freed_bytes,
        "freed_mb": freed_mb,
        "videos_removed": videos_removed,
        "evidence_removed": evidence_removed,
        "max_age_days": max_age_days,
    }
