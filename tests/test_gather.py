"""
Integration tests for gather() — parallel step execution within workflows.

RED STATE — all tests are expected to fail with NotImplementedError because
asyncai/gather.py contains a stub implementation only.

Requirements covered: GTHR-01, GTHR-02, GTHR-03, GTHR-04, GTHR-05, GTHR-06
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from asyncai.gather import gather
from asyncai.task import task
from asyncai._context import _active_workflow_id
from asyncai.db.models import Job, JobStatus
from asyncai.db.session import AsyncSessionFactory
from asyncai.worker import AsyncWorker
from asyncai.exceptions import WorkflowError

# ---------------------------------------------------------------------------
# Module-level marker — all tests require a live DB
# ---------------------------------------------------------------------------
pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Task helpers used across tests
# ---------------------------------------------------------------------------

@task
async def add_one(x: int) -> dict:
    """Simple task that adds one — used as a child job in gather tests."""
    return {"result": x + 1}


@task(retries=1)
async def always_fails(x: int) -> dict:
    """Task that always raises — used to verify gather() failure handling."""
    raise ValueError("intentional failure")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gather_submits_linked_jobs(async_db_session):
    """GTHR-01: gather() inside a workflow body creates child Job rows with workflow_id and step_name set."""
    workflow_id = uuid.uuid4()
    token = _active_workflow_id.set(workflow_id)
    try:
        results = await gather(
            [add_one.submit(x=1), add_one.submit(x=2)],
            step_name="step1",
        )
    except NotImplementedError:
        # Expected in RED state — but we still want the test to FAIL, not ERROR
        pytest.fail("gather() raised NotImplementedError — stub not yet replaced")
    finally:
        _active_workflow_id.reset(token)

    # Verify DB: two child jobs linked to workflow_id with step_name="step1"
    async with AsyncSessionFactory() as session:
        job_result = await session.execute(
            select(Job).where(
                Job.workflow_id == workflow_id,
                Job.step_name == "step1",
            )
        )
        jobs = job_result.scalars().all()
        assert len(jobs) == 2, f"Expected 2 child jobs, got {len(jobs)}"


@pytest.mark.asyncio
async def test_gather_waits_for_completion(async_db_session):
    """GTHR-02: gather() does not return until all child jobs reach COMPLETED or FAILED."""
    workflow_id = uuid.uuid4()
    token = _active_workflow_id.set(workflow_id)

    worker = AsyncWorker(concurrency=2)

    try:
        # Run gather concurrently with the worker
        import asyncio as _asyncio
        gather_task = _asyncio.create_task(
            gather([add_one.submit(x=10), add_one.submit(x=20)], step_name="wait_step")
        )
        # Give gather a moment to submit jobs before running the worker
        await _asyncio.sleep(0.05)
        await worker.run_until_empty()
        results = await gather_task
    except NotImplementedError:
        pytest.fail("gather() raised NotImplementedError — stub not yet replaced")
    finally:
        _active_workflow_id.reset(token)

    assert results is not None, "gather() must return results after all jobs complete"


@pytest.mark.asyncio
async def test_gather_ordered_results(async_db_session):
    """GTHR-03: gather() returns results in submission order regardless of completion order."""
    workflow_id = uuid.uuid4()
    token = _active_workflow_id.set(workflow_id)

    worker = AsyncWorker(concurrency=2)

    try:
        import asyncio as _asyncio
        gather_task = _asyncio.create_task(
            gather([add_one.submit(x=1), add_one.submit(x=2)], step_name="order")
        )
        await _asyncio.sleep(0.05)
        await worker.run_until_empty()
        results = await gather_task
    except NotImplementedError:
        pytest.fail("gather() raised NotImplementedError — stub not yet replaced")
    finally:
        _active_workflow_id.reset(token)

    assert results == [{"result": 2}, {"result": 3}], (
        f"Results must be in submission order: [{{result: 2}}, {{result: 3}}], got {results}"
    )


@pytest.mark.asyncio
async def test_gather_raises_on_failure(async_db_session):
    """GTHR-04: If any child job exhausts retries and reaches FAILED, gather() raises WorkflowError."""
    workflow_id = uuid.uuid4()
    token = _active_workflow_id.set(workflow_id)

    worker = AsyncWorker(concurrency=2)

    try:
        import asyncio as _asyncio
        gather_task = _asyncio.create_task(
            gather([always_fails.submit(x=1)], step_name="fail_step")
        )
        await _asyncio.sleep(0.05)
        await worker.run_until_empty()
        with pytest.raises(WorkflowError):
            await gather_task
    except NotImplementedError:
        pytest.fail("gather() raised NotImplementedError — stub not yet replaced")
    finally:
        _active_workflow_id.reset(token)


@pytest.mark.asyncio
async def test_gather_timeout(async_db_session):
    """GTHR-05: gather() raises TimeoutError when child jobs are stuck PENDING and timeout elapses."""
    workflow_id = uuid.uuid4()
    token = _active_workflow_id.set(workflow_id)

    try:
        # Do NOT run worker — jobs stay PENDING indefinitely
        with pytest.raises(TimeoutError):
            await gather(
                [add_one.submit(x=99)],
                step_name="timeout_step",
                timeout=0.1,
            )
    except NotImplementedError:
        pytest.fail("gather() raised NotImplementedError — stub not yet replaced")
    finally:
        _active_workflow_id.reset(token)


@pytest.mark.asyncio
async def test_gather_idempotent_restart(async_db_session):
    """GTHR-06: Calling gather() twice with the same workflow_id + step_name does not create duplicate jobs."""
    workflow_id = uuid.uuid4()
    token = _active_workflow_id.set(workflow_id)

    worker = AsyncWorker(concurrency=2)

    try:
        import asyncio as _asyncio

        # First gather call — submits jobs
        gather_task_1 = _asyncio.create_task(
            gather([add_one.submit(x=5), add_one.submit(x=6)], step_name="idempotent")
        )
        await _asyncio.sleep(0.05)
        await worker.run_until_empty()
        results_1 = await gather_task_1

        # Second gather call — same workflow_id + step_name — must NOT create new jobs
        gather_task_2 = _asyncio.create_task(
            gather([add_one.submit(x=5), add_one.submit(x=6)], step_name="idempotent")
        )
        await worker.run_until_empty()
        results_2 = await gather_task_2

        # Assert: still exactly 2 jobs for (workflow_id, step_name="idempotent")
        async with AsyncSessionFactory() as session:
            job_result = await session.execute(
                select(Job).where(
                    Job.workflow_id == workflow_id,
                    Job.step_name == "idempotent",
                )
            )
            jobs = job_result.scalars().all()
            assert len(jobs) == 2, (
                f"Second gather() must reuse existing jobs, not create duplicates. "
                f"Expected 2 jobs, got {len(jobs)}"
            )

        assert results_1 == results_2, "Both gather() calls must return identical results"

    except NotImplementedError:
        pytest.fail("gather() raised NotImplementedError — stub not yet replaced")
    finally:
        _active_workflow_id.reset(token)
