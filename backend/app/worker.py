"""Background worker: polls the Postgres job queue and runs jobs.

Also performs janitorial expiry of prepared worlds (PLAN §3.5 retention).

Run with: ``python -m app.worker``
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.models.enums import PreparedWorldStatus
from app.models.world import PreparedWorld
from app.seed import run_seeds
from app.services import jobs
from app.services.jobs import JOB_PREPARE_WORLD
from app.services.storage import get_storage
from app.services.worldprep import process_prepared_world

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
log = logging.getLogger("worker")

POLL_INTERVAL_SECONDS = 2
JANITOR_INTERVAL_SECONDS = 300

_HANDLERS = {
    JOB_PREPARE_WORLD: lambda db, payload: process_prepared_world(
        db, payload["prepared_world_id"]
    ),
}


def run_once() -> bool:
    """Claim and run a single job. Returns True if a job was processed."""
    db = SessionLocal()
    try:
        job = jobs.claim_next(db)
        if job is None:
            return False
        log.info("Running job %s (%s)", job.id, job.job_type)
        try:
            handler = _HANDLERS.get(job.job_type)
            if handler is None:
                raise ValueError(f"Unknown job type: {job.job_type}")
            handler(db, job.payload)
            jobs.mark_done(db, job)
            log.info("Job %s done", job.id)
        except Exception as exc:  # noqa: BLE001
            log.exception("Job %s failed", job.id)
            db.rollback()
            jobs.mark_failed(db, job, str(exc))
        return True
    finally:
        db.close()


def run_janitor() -> None:
    """Expire prepared worlds past their TTL: delete the B2 object, mark expired."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        stale = (
            db.execute(
                select(PreparedWorld).where(
                    PreparedWorld.status == PreparedWorldStatus.ready,
                    PreparedWorld.expires_at.is_not(None),
                    PreparedWorld.expires_at < now,
                )
            )
            .scalars()
            .all()
        )
        if not stale:
            return
        storage = get_storage()
        for pw in stale:
            if pw.b2_key:
                try:
                    storage.delete(pw.b2_key)
                except Exception:
                    log.warning("Failed to delete B2 object for %s", pw.id)
            pw.status = PreparedWorldStatus.expired
            pw.b2_key = None
        db.commit()
        log.info("Expired %d prepared world(s)", len(stale))
    finally:
        db.close()


def main() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_seeds(db)
    finally:
        db.close()

    log.info("Worker started")
    last_janitor = 0.0
    while True:
        did_work = run_once()
        now = time.monotonic()
        if now - last_janitor > JANITOR_INTERVAL_SECONDS:
            try:
                run_janitor()
            except Exception:
                log.exception("Janitor pass failed")
            last_janitor = now
        if not did_work:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
