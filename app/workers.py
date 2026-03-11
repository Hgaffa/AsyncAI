"""Worker functions for background job processing (synchronous / legacy)."""
import logging
import os
import random
import time
import datetime

from dotenv import load_dotenv
from prometheus_client import start_http_server
from sqlalchemy import asc, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import SESSIONLOCAL
from app.metrics import (
    job_duration_histogram,
    job_queue_wait_histogram,
    jobs_completed_counter,
    jobs_failed_counter,
    jobs_pending_gauge,
    jobs_processing_gauge,
    jobs_retried_counter,
    worker_up_gauge,
)
from app.models import Job
from app.schemas import JobStatus

load_dotenv()
WORKER_METRICS_PORT = int(os.getenv("WORKER_METRICS_PORT", "8001"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class JobExecutionError(Exception):
    """Raised when a job handler encounters an execution-time failure."""


class UnknownJobTypeError(ValueError):
    """Raised when the job type has no registered handler."""


# ---------------------------------------------------------------------------
# Job handlers — defined at module level to avoid rebuilding the dispatch
# table on every call.
# ---------------------------------------------------------------------------

def handle_send_email(payload: dict) -> dict:
    """Simulate sending an email (20 % transient failure rate)."""
    time.sleep(2)
    if random.random() < 0.2:
        raise JobExecutionError("Email service temporarily unavailable")
    return {"sent_to": payload.get("to"), "status": "sent"}


def handle_process_data(payload: dict) -> dict:
    """Simulate processing data (20 % transient failure rate)."""
    time.sleep(2)
    if random.random() < 0.2:
        raise JobExecutionError("Process data service temporarily unavailable")
    return {"data": payload.get("data"), "status": "processed"}


def handle_always_fail(payload: dict) -> dict:
    """Always fails — used to exercise retry logic in tests."""
    time.sleep(1)
    raise JobExecutionError("This job type is designed to always fail")


_HANDLERS = {
    "send_email": handle_send_email,
    "process_data": handle_process_data,
    "test_failure": handle_always_fail,
}


def execute_job(job: Job):
    """Route *job* to the appropriate handler based on its type.

    Raises:
        UnknownJobTypeError: If ``job.type`` has no registered handler.
    """
    handler = _HANDLERS.get(job.type)
    if not handler:
        raise UnknownJobTypeError(f"Unknown job type: {job.type}")
    return handler(job.payload)


# ---------------------------------------------------------------------------
# Worker logic
# ---------------------------------------------------------------------------

def process_next_job(db: Session) -> None:
    """Fetch the next eligible PENDING job and execute it.

    Jobs are ordered by descending priority (higher number = higher priority),
    then by creation time so earlier-submitted jobs are processed first when
    priority is equal.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    job: Job = (
        db.query(Job)
        .filter(
            Job.status == JobStatus.PENDING,
            or_(
                Job.scheduled_at.is_(None),
                Job.scheduled_at <= now,
            ),
        )
        .order_by(Job.priority.desc(), asc(Job.created_at))
        .first()
    )

    if job is None:
        logger.info("No jobs ready to process")
        return

    queue_wait = (now - job.created_at).total_seconds()
    job_queue_wait_histogram.labels(job_type=job.type).observe(queue_wait)
    logger.info(
        "Processing job %s (type=%s priority=%s waited=%.2fs)",
        job.id, job.type, job.priority, queue_wait,
    )
    if job.scheduled_at:
        logger.info("Job was scheduled for %s", job.scheduled_at.isoformat())

    job.status = JobStatus.PROCESSING
    job.started_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    start_time = time.monotonic()
    try:
        result = execute_job(job)
        duration = time.monotonic() - start_time
        logger.info("Job %s completed in %.2fs", job.id, duration)

        job.status = JobStatus.COMPLETED
        job.result = result
        job.finished_at = datetime.datetime.now(datetime.timezone.utc)
        jobs_completed_counter.labels(job_type=job.type).inc()
        job_duration_histogram.labels(job_type=job.type).observe(duration)

    except (JobExecutionError, UnknownJobTypeError) as exc:
        duration = time.monotonic() - start_time
        logger.error("Job %s failed after %.2fs: %s", job.id, duration, exc)

        job.attempts += 1
        if job.attempts >= job.max_attempts:
            logger.error(
                "Job %s exhausted %s/%s attempts — marking FAILED",
                job.id, job.attempts, job.max_attempts,
            )
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            job.finished_at = datetime.datetime.now(datetime.timezone.utc)
            jobs_failed_counter.labels(job_type=job.type).inc()
            job_duration_histogram.labels(job_type=job.type).observe(duration)
        else:
            logger.info(
                "Job %s will retry (attempt %s/%s)",
                job.id, job.attempts, job.max_attempts,
            )
            job.status = JobStatus.PENDING
            job.error_message = f"Attempt {job.attempts} failed: {exc}"
            jobs_retried_counter.labels(job_type=job.type).inc()

    finally:
        job.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()


def update_state_gauges(db: Session) -> None:
    """Refresh the PENDING/PROCESSING gauge metrics from the current DB state."""
    jobs_pending_gauge.set(
        db.query(Job).filter(Job.status == JobStatus.PENDING).count()
    )
    jobs_processing_gauge.set(
        db.query(Job).filter(Job.status == JobStatus.PROCESSING).count()
    )


def recover_stuck_jobs(db: Session) -> None:
    """Reset all PROCESSING jobs to PENDING on worker startup.

    A single UPDATE is used rather than loading all rows, keeping the
    operation efficient even with many stuck jobs.
    """
    updated = (
        db.query(Job)
        .filter(Job.status == JobStatus.PROCESSING)
        .update({"status": JobStatus.PENDING})
    )
    db.commit()
    if updated:
        logger.warning("Recovered %s stuck job(s) from previous crash", updated)
    else:
        logger.info("No stuck jobs found — clean startup")


def worker_loop() -> None:
    """Main worker loop: start metrics server, recover crashed jobs, then poll."""
    db = SESSIONLOCAL()
    try:
        logger.info("Starting metrics server on port %s", WORKER_METRICS_PORT)
        start_http_server(WORKER_METRICS_PORT)

        # Wait for the database to be ready with exponential-style back-off.
        max_retries = 10
        for attempt in range(1, max_retries + 1):
            try:
                recover_stuck_jobs(db)
                logger.info("Database connection established")
                break
            except SQLAlchemyError as exc:
                logger.warning(
                    "Database not ready (attempt %s/%s): %s",
                    attempt, max_retries, exc,
                )
                if attempt == max_retries:
                    logger.error("Failed to connect after %s attempts", max_retries)
                    raise
                time.sleep(2)

        worker_up_gauge.set(1)

        while True:
            process_next_job(db)
            update_state_gauges(db)
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Worker shutting down gracefully")
        worker_up_gauge.set(0)

    finally:
        db.close()


if __name__ == "__main__":
    worker_loop()
