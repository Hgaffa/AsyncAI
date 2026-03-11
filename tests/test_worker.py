import pytest
import pytest_asyncio
import asyncio

# All tests in this file require asyncai.worker (does not exist until Plan 03)
# Running this file in RED state should produce ImportError or collection errors.


@pytest.mark.asyncio
@pytest.mark.integration
async def test_worker_empty_queue(async_db_session):
    from asyncai.worker import AsyncWorker
    worker = AsyncWorker(concurrency=1)
    # Should return without error when no PENDING jobs exist
    await worker.run_until_empty()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_skip_locked_no_duplicate(async_db_session):
    from asyncai.task import task
    from asyncai.worker import poll_and_run_one
    from asyncai.db.models import Job, JobStatus
    from sqlalchemy import select

    @task
    async def locked_task(x: int): return x

    job_id = await locked_task.submit(x=1)

    # Two concurrent claims — each call owns its own session/connection,
    # so SKIP LOCKED works: only one should succeed, the other returns None
    results = await asyncio.gather(
        poll_and_run_one(),
        poll_and_run_one(),
    )
    claimed = [r for r in results if r is not None]
    assert len(claimed) == 1
    assert claimed[0] == job_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_worker_dispatches(async_db_session):
    from asyncai.task import task
    from asyncai.worker import poll_and_run_one

    dispatched = []

    @task
    async def dispatch_target(value: int):
        dispatched.append(value)
        return value

    await dispatch_target.submit(value=99)
    await poll_and_run_one()
    assert dispatched == [99]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_worker_success(async_db_session):
    from asyncai.task import task
    from asyncai.worker import poll_and_run_one
    from asyncai.db.models import Job, JobStatus, TaskResult
    from sqlalchemy import select

    @task
    async def success_task(n: int): return {"doubled": n * 2}

    job_id = await success_task.submit(n=5)
    await poll_and_run_one()

    job = await async_db_session.get(Job, job_id)
    assert job.status == JobStatus.COMPLETED

    result = await async_db_session.execute(
        select(TaskResult).where(TaskResult.job_id == job_id)
    )
    row = result.scalar_one()
    assert row.value == {"doubled": 10}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_worker_retries(async_db_session):
    from asyncai.task import task
    from asyncai.worker import poll_and_run_one
    from asyncai.db.models import Job, JobStatus

    @task(retries=2)
    async def flaky_task(x: int):
        raise ValueError("always fails")

    job_id = await flaky_task.submit(x=1)

    # First attempt: attempts=1, status=PENDING (retryable)
    await poll_and_run_one()
    job = await async_db_session.get(Job, job_id)
    assert job.attempts == 1
    assert job.status == JobStatus.PENDING

    # Second attempt: attempts=2, status=FAILED (exhausted)
    await poll_and_run_one()
    await async_db_session.refresh(job)
    assert job.attempts == 2
    assert job.status == JobStatus.FAILED
    assert "always fails" in (job.error_message or "")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_crash_recovery(async_db_session):
    from asyncai.worker import recover_crashed_jobs
    from asyncai.db.models import Job, JobStatus
    import datetime

    # Manually insert a PROCESSING job (simulates crashed worker)
    stuck = Job(
        type="phantom_task",
        status=JobStatus.PROCESSING,
        payload={},
        started_at=datetime.datetime.now(datetime.timezone.utc),
    )
    async_db_session.add(stuck)
    await async_db_session.flush()
    stuck_id = stuck.id

    await recover_crashed_jobs(async_db_session)
    await async_db_session.refresh(stuck)
    assert stuck.status == JobStatus.PENDING


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrency(async_db_session):
    from asyncai.task import task
    from asyncai.worker import AsyncWorker
    from asyncai.db.models import Job, JobStatus
    from sqlalchemy import select

    processed = []

    @task
    async def concurrent_task(i: int):
        processed.append(i)
        return i

    # Submit 4 jobs
    for i in range(4):
        await concurrent_task.submit(i=i)

    worker = AsyncWorker(concurrency=4)
    await worker.run_until_empty()

    assert len(processed) == 4


@pytest.mark.asyncio
@pytest.mark.integration
async def test_metrics_updated(async_db_session):
    from asyncai.task import task
    from asyncai.worker import poll_and_run_one
    from asyncai.metrics import jobs_completed_counter, jobs_failed_counter

    @task
    async def metric_ok(x: int): return x

    @task(retries=1)
    async def metric_fail(x: int): raise RuntimeError("fail")

    before_ok = jobs_completed_counter.labels(job_type="metric_ok")._value.get()
    before_fail = jobs_failed_counter.labels(job_type="metric_fail")._value.get()

    await metric_ok.submit(x=1)
    await poll_and_run_one()
    assert jobs_completed_counter.labels(job_type="metric_ok")._value.get() == before_ok + 1

    await metric_fail.submit(x=1)
    await poll_and_run_one()  # attempt 1 (retryable)
    await poll_and_run_one()  # attempt 2 (final fail)
    assert jobs_failed_counter.labels(job_type="metric_fail")._value.get() == before_fail + 1
