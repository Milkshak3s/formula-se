"""Postgres-backed job queue helpers (SELECT ... FOR UPDATE SKIP LOCKED)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job

JOB_PREPARE_WORLD = "prepare_world"


def enqueue(db: Session, job_type: str, payload: dict[str, Any]) -> Job:
    job = Job(job_type=job_type, payload=payload, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next(db: Session) -> Job | None:
    """Atomically claim the next runnable job, or return None.

    Uses row-level locking so multiple workers never grab the same job.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(Job)
        .where(Job.status == "queued", Job.run_after <= now)
        .order_by(Job.run_after)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.execute(stmt).scalars().first()
    if job is None:
        db.commit()
        return None
    job.status = "running"
    job.attempts += 1
    job.started_at = now
    db.commit()
    db.refresh(job)
    return job


def mark_done(db: Session, job: Job) -> None:
    job.status = "done"
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def mark_failed(db: Session, job: Job, error: str) -> None:
    job.error = error[:2000]
    if job.attempts >= job.max_attempts:
        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
    else:
        job.status = "queued"  # retry
    db.commit()
