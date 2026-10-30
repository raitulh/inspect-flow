import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import AnalysisJob, InspectionRule, VideoAsset
from app.vision.opencv_rules import analyze_video

logger = logging.getLogger("lineguard.worker")


def run_analysis_job(job_id: str) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        if not job or job.status not in {"queued", "running"}:
            return
        video = db.get(VideoAsset, job.video_id)
        if not video:
            job.status = "failed"
            job.error_message = "Video asset record no longer exists"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.progress = 5
        db.commit()
        try:
            rules = list(db.scalars(select(InspectionRule).where(
                InspectionRule.organization_id == job.organization_id,
                InspectionRule.station_id == job.station_id,
            )).all())
            summary = analyze_video(db, job, video, rules, settings.storage_root)
            job.result_summary = json.dumps(summary)
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(AnalysisJob, job_id)
            if job:
                job.status = "failed"
                job.progress = 100
                if isinstance(exc, ValueError):
                    job.error_message = str(exc)[:220]
                else:
                    job.error_message = "Video analysis failed. Check server logs using the job ID."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            logger.exception("Analysis job %s failed", job_id)


def recover_stale_jobs(max_age_minutes: int = 60) -> int:
    """Requeue jobs left running after a worker crash, with a conservative age limit."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    with SessionLocal() as db:
        stale = list(db.scalars(select(AnalysisJob).where(
            AnalysisJob.status == "running",
            AnalysisJob.started_at.is_not(None),
            AnalysisJob.started_at < cutoff,
        )).all())
        for job in stale:
            job.status = "queued"
            job.progress = 0
            job.started_at = None
            job.error_message = "Requeued after worker recovery; previous execution did not finish."
        db.commit()
        return len(stale)


def claim_next_job() -> str | None:
    """Claim one queued job. Run one worker per SQLite database; PostgreSQL supports SKIP LOCKED."""
    with SessionLocal() as db:
        stmt = select(AnalysisJob).where(AnalysisJob.status == "queued").order_by(AnalysisJob.created_at).limit(1)
        if not get_settings().database_url.startswith("sqlite"):
            stmt = stmt.with_for_update(skip_locked=True)
        job = db.scalar(stmt)
        if not job:
            return None
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.progress = 1
        db.commit()
        return job.id


def process_claimed_job(job_id: str) -> None:
    # run_analysis_job accepts both queued and running states and preserves the claim state.
    run_analysis_job(job_id)


def worker_loop() -> None:
    import time

    logger.info("LineGuard worker started; recovered %s stale jobs", recover_stale_jobs())
    while True:
        job_id = claim_next_job()
        if job_id:
            process_claimed_job(job_id)
        else:
            time.sleep(get_settings().worker_poll_seconds)
