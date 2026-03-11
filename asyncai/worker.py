"""
Async job worker for asyncai.

Provides:
  - ``recover_crashed_jobs`` — reset PROCESSING → PENDING on startup
  - ``poll_and_run_one``     — claim and execute one PENDING job
  - ``AsyncWorker``          — bounded-concurrency worker that drains the queue
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from asyncai.db.models import Job, JobStatus, TaskResult
from asyncai.db.session import AsyncSessionFactory
from asyncai.metrics import jobs_completed_counter, jobs_failed_counter
from asyncai.registry import TaskRegistry


async def recover_crashed_jobs(session: AsyncSession) -> None:
    """Reset all PROCESSING jobs back to PENDING.

    Call this on worker startup to reclaim jobs that were in-flight when the
    previous worker process crashed without completing or failing them.

    Args:
        session: An active ``AsyncSession`` (caller manages its transaction).
    """
    await session.execute(
        update(Job)
        .where(Job.status == JobStatus.PROCESSING)
        .values(
            status=JobStatus.PENDING,
            finished_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )


async def poll_and_run_one() -> int | None:
    """Claim and execute one PENDING job using its own session.

    Uses a two-transaction pattern within a single session:

    - **Tx1** — ``SELECT FOR UPDATE SKIP LOCKED`` to atomically claim the
      highest-priority PENDING job and mark it PROCESSING.
    - **Tx2** — Dispatch to the registered task function, then persist the
      outcome (COMPLETED + TaskResult, or FAILED/PENDING for retry).

    Each call owns its session so concurrent callers get separate DB
    connections — a requirement for SKIP LOCKED to prevent duplicate claims.

    Returns:
        The ``job.id`` that was processed, or ``None`` if the queue was empty.
    """
    async with AsyncSessionFactory() as session:
        # Tx1: atomically claim one job
        async with session.begin():
            result = await session.execute(
                select(Job)
                .where(Job.status == JobStatus.PENDING)
                .order_by(Job.priority.desc(), Job.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job = result.scalar_one_or_none()
            if job is None:
                return None
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.datetime.now(datetime.timezone.utc)
            job_id = job.id

        # Tx2: execute and persist outcome
        async with session.begin():
            job = await session.get(Job, job_id, with_for_update=True)
            try:
                fn = TaskRegistry.instance().get(job.type)
                return_value: Any = await fn(**job.payload)
                job.status = JobStatus.COMPLETED
                job.finished_at = datetime.datetime.now(datetime.timezone.utc)
                # Store the result; wrap scalars in a dict so JSONB is always
                # given a JSON object, falling back to {} for None returns.
                result_value = (
                    return_value
                    if isinstance(return_value, dict)
                    else ({} if return_value is None else {"result": return_value})
                )
                session.add(TaskResult(job_id=job.id, value=result_value))
                jobs_completed_counter.labels(job_type=job.type).inc()
            except Exception as exc:  # noqa: BLE001
                job.attempts += 1
                job.error_message = str(exc)
                job.finished_at = datetime.datetime.now(datetime.timezone.utc)
                if job.attempts >= job.max_attempts:
                    job.status = JobStatus.FAILED
                    jobs_failed_counter.labels(job_type=job.type).inc()
                else:
                    job.status = JobStatus.PENDING

    return job_id


class AsyncWorker:
    """Bounded-concurrency worker that drains the job queue.

    Uses an ``asyncio.Semaphore`` to cap the number of concurrently executing
    jobs. Each job runs in its own DB session so SKIP LOCKED works correctly
    across concurrent coroutines.

    Args:
        concurrency: Maximum number of jobs that may execute simultaneously.
    """

    def __init__(self, concurrency: int = 10) -> None:
        self._concurrency = concurrency
        self._semaphore = asyncio.Semaphore(concurrency)

    async def _run_one(self) -> int | None:
        async with self._semaphore:
            return await poll_and_run_one()

    async def run_until_empty(self) -> None:
        """Poll and run jobs until the queue is empty.

        Launches up to ``concurrency`` concurrent job coroutines per round,
        stopping when an entire round returns no work.
        """
        while True:
            results = await asyncio.gather(
                *[self._run_one() for _ in range(self._concurrency)]
            )
            if all(r is None for r in results):
                break


__all__ = ["recover_crashed_jobs", "poll_and_run_one", "AsyncWorker"]
