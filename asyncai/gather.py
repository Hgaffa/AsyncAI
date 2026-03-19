"""
gather() coroutine for asyncai workflows.

Implements parallel task fan-out with ordered results, failure propagation,
timeout, and idempotent restart.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Coroutine

from sqlalchemy import select

from asyncai._context import _active_step_name, _active_workflow_id
from asyncai.db.models import Job, JobStatus, TaskResult, Workflow, WorkflowStatus
from asyncai.db.session import AsyncSessionFactory
from asyncai.exceptions import WorkflowError


async def gather(
    submissions: list[Coroutine[Any, Any, int]],
    *,
    step_name: str,
    poll_interval: float = 0.5,
    timeout: float = 600.0,
) -> list[Any]:
    """
    Submit a list of job coroutines and wait for all to complete.

    Parameters
    ----------
    submissions:
        List of coroutines returned by task.submit() calls (awaitable ints / job IDs).
        Each coroutine, when awaited, inserts a Job row and returns its int id.
    step_name:
        Logical name for this parallel step — used for idempotent restart detection.
        Must be unique within a single workflow execution.
    poll_interval:
        Seconds between DB status polls while waiting for jobs to finish.
    timeout:
        Maximum seconds to wait before raising TimeoutError.

    Returns
    -------
    list
        Results in submission order once all jobs reach COMPLETED.

    Raises
    ------
    WorkflowError
        If gather() is called outside a @workflow function (no active workflow_id),
        or if any child job reaches FAILED status after exhausting retries.
    TimeoutError
        When ``timeout`` is exceeded before all jobs complete.
    """
    # Guard — must be called inside a @workflow function
    workflow_id = _active_workflow_id.get()
    if workflow_id is None:
        # Close all unawaited coroutines to suppress "coroutine was never awaited" warnings
        for coro in submissions:
            coro.close()
        raise WorkflowError("gather() must be called inside a @workflow function")

    # Ensure the Workflow row exists (required by FK constraint on job.workflow_id).
    # When gather() is called directly in tests (bypassing the @workflow runner), the row
    # may not exist yet — check first to avoid a duplicate insert.
    async with AsyncSessionFactory() as session:
        async with session.begin():
            existing_wf = await session.get(Workflow, workflow_id)
            if existing_wf is None:
                session.add(Workflow(id=workflow_id, status=WorkflowStatus.RUNNING))

    # Idempotency check — look for existing child jobs for this step
    async with AsyncSessionFactory() as session:
        existing_result = await session.execute(
            select(Job)
            .where(Job.workflow_id == workflow_id)
            .where(Job.step_name == step_name)
            .order_by(Job.id.asc())
        )
        existing_jobs = existing_result.scalars().all()

    job_ids: list[int]
    if existing_jobs:
        # Reuse existing job IDs — close unawaited coroutines to avoid warnings
        for coro in submissions:
            coro.close()
        job_ids = [j.id for j in existing_jobs]
    else:
        # Submit each coroutine with workflow context set in ContextVars.
        # _active_workflow_id is already set by the caller; set _active_step_name here so
        # submit() picks up both values and writes them atomically at Job creation time —
        # no separate UPDATE transaction required.
        job_ids = []
        step_name_token = _active_step_name.set(step_name)
        try:
            for coro in submissions:
                job_id = await coro
                job_ids.append(job_id)
        finally:
            _active_step_name.reset(step_name_token)

    # Spawn an inline worker to process submitted jobs.
    # This allows gather() to work without an external worker process — important
    # for tests and simple usage. The inline worker races with any external worker;
    # SKIP LOCKED on the worker's SELECT ensures each job is processed exactly once.
    from asyncai.worker import AsyncWorker  # local import to avoid circular deps at module load

    inline_worker = AsyncWorker(concurrency=max(len(job_ids), 1))
    inline_worker_task = asyncio.create_task(inline_worker.run_until_empty())

    # Poll loop — wait for all jobs to reach a terminal state
    deadline = time.monotonic() + timeout

    try:
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"gather() step '{step_name}' timed out after {timeout}s"
                )

            async with AsyncSessionFactory() as session:
                poll_result = await session.execute(
                    select(Job).where(Job.id.in_(job_ids))
                )
                jobs = poll_result.scalars().all()

            for job in jobs:
                if job.status == JobStatus.FAILED:
                    raise WorkflowError(
                        job.error_message or f"Child job {job.id} failed with no error message"
                    )

            # Check if all jobs completed
            if all(job.status == JobStatus.COMPLETED for job in jobs):
                break

            await asyncio.sleep(poll_interval)
    finally:
        # Cancel inline worker if gather exits (normally or via exception)
        if not inline_worker_task.done():
            inline_worker_task.cancel()
            try:
                await inline_worker_task
            except (asyncio.CancelledError, Exception):
                pass

    # Fetch results in submission order
    results: list[Any] = []
    async with AsyncSessionFactory() as session:
        for job_id in job_ids:
            tr_result = await session.execute(
                select(TaskResult).where(TaskResult.job_id == job_id)
            )
            tr = tr_result.scalar_one_or_none()
            if tr is None:
                results.append(None)
            else:
                results.append(tr.value)

    return results


__all__ = ["gather"]
