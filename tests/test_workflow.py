"""
Integration tests for the @workflow decorator and WorkflowHandle.

RED STATE — all tests are expected to fail with NotImplementedError because
asyncai/workflow.py contains a stub implementation only.

Requirements covered: WF-01, WF-02, WF-03, WF-04

Plan 05-02 additions: unit-level tests for branches not covered by integration
tests (WorkflowHandle.status not found, WorkflowHandle.result not found,
WorkflowWrapper.__call__, @workflow() with parentheses).
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from asyncai.workflow import workflow, WorkflowHandle
from asyncai._context import _active_workflow_id
from asyncai.db.models import Workflow, WorkflowStatus, Job, JobStatus
from asyncai.db.session import AsyncSessionFactory
from asyncai.worker import AsyncWorker
from asyncai.exceptions import WorkflowError

# ---------------------------------------------------------------------------
# Module-level marker — all tests in this file require a live DB
# (overridden per-test for unit-level tests)
# ---------------------------------------------------------------------------
pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Unit-level tests (no DB required) — cover branches missed by integration suite
# ---------------------------------------------------------------------------


def test_workflow_with_parentheses_registers():
    """@workflow() with empty parentheses must register the function (line 218 branch)."""
    @workflow()
    async def parenthesised_workflow(x: int) -> dict:
        return {"x": x}

    # If the decorator path works correctly the wrapper has .submit
    assert hasattr(parenthesised_workflow, "submit")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_workflow_wrapper_is_callable():
    """WorkflowWrapper.__call__ must delegate to the underlying function (line 167)."""
    @workflow
    async def callable_workflow(x: int) -> int:
        return x * 3

    result = await callable_workflow(x=4)
    assert result == 12


@pytest.mark.asyncio
@pytest.mark.unit
async def test_workflow_handle_status_not_found():
    """WorkflowHandle.status() must raise WorkflowError when the row doesn't exist (line 37)."""
    from unittest.mock import AsyncMock, patch, MagicMock

    non_existent_id = uuid.uuid4()
    handle = WorkflowHandle(id=non_existent_id)

    # Mock the session so it returns None for the workflow
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("asyncai.workflow.AsyncSessionFactory", return_value=mock_cm):
        with pytest.raises(WorkflowError, match=str(non_existent_id)):
            await handle.status()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_workflow_handle_result_not_found():
    """WorkflowHandle.result() must raise WorkflowError when the row doesn't exist (line 60)."""
    from unittest.mock import AsyncMock, patch, MagicMock

    non_existent_id = uuid.uuid4()
    handle = WorkflowHandle(id=non_existent_id)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("asyncai.workflow.AsyncSessionFactory", return_value=mock_cm):
        with pytest.raises(WorkflowError, match=str(non_existent_id)):
            await handle.result(timeout=1.0)


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

@workflow
async def double_workflow(x: int) -> dict:
    """Simple workflow that doubles its input."""
    return {"result": x * 2}


@workflow
async def failing_workflow(x: int) -> dict:
    """Workflow that always raises, used to verify error propagation."""
    raise ValueError(f"intentional failure: {x}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_submit(async_db_session):
    """WF-01: Submitting a workflow creates one Workflow row and one Job row.

    Returns a WorkflowHandle with a valid UUID id.
    """
    handle = await double_workflow.submit(x=1)

    assert isinstance(handle, WorkflowHandle), "submit() must return a WorkflowHandle"
    assert isinstance(handle.id, uuid.UUID), "WorkflowHandle.id must be a UUID"

    # Verify DB state
    async with AsyncSessionFactory() as session:
        wf_row = await session.get(Workflow, handle.id)
        assert wf_row is not None, "Workflow row must be created in DB"

        job_result = await session.execute(
            select(Job).where(Job.workflow_id == handle.id)
        )
        jobs = job_result.scalars().all()
        assert len(jobs) == 1, "Exactly one Job row must be linked to the workflow"


@pytest.mark.asyncio
async def test_workflow_handle_id(async_db_session):
    """WF-01: WorkflowHandle.id is a uuid.UUID type."""
    handle = await double_workflow.submit(x=5)

    assert isinstance(handle.id, uuid.UUID)


@pytest.mark.asyncio
async def test_workflow_status_poll(async_db_session):
    """WF-02: handle.status() returns a WorkflowStatus enum value (PENDING or RUNNING initially)."""
    handle = await double_workflow.submit(x=3)

    status = await handle.status()

    assert isinstance(status, WorkflowStatus), "status() must return a WorkflowStatus"
    assert status in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING), (
        f"Status should be PENDING or RUNNING immediately after submit, got {status}"
    )


@pytest.mark.asyncio
async def test_workflow_result_returns(async_db_session):
    """WF-02: After the worker processes the workflow, handle.result() returns the workflow's return value."""
    handle = await double_workflow.submit(x=4)

    worker = AsyncWorker(concurrency=1)
    await worker.run_until_empty()

    result = await handle.result(timeout=30.0)
    assert result == {"result": 8}, f"Expected {{'result': 8}}, got {result}"


@pytest.mark.asyncio
async def test_workflow_executes(async_db_session):
    """WF-03: Worker picks up the workflow job and updates Workflow row to COMPLETED."""
    handle = await double_workflow.submit(x=2)

    worker = AsyncWorker(concurrency=1)
    await worker.run_until_empty()

    async with AsyncSessionFactory() as session:
        wf_row = await session.get(Workflow, handle.id)
        assert wf_row is not None
        assert wf_row.status == WorkflowStatus.COMPLETED, (
            f"Workflow status should be COMPLETED after execution, got {wf_row.status}"
        )
        assert wf_row.result == {"result": 4}, (
            f"Workflow result should be stored, got {wf_row.result}"
        )


@pytest.mark.asyncio
async def test_workflow_error_propagates(async_db_session):
    """WF-04: When the workflow function raises, handle.result() re-raises WorkflowError."""
    handle = await failing_workflow.submit(x=7)

    worker = AsyncWorker(concurrency=1)
    await worker.run_until_empty()

    with pytest.raises(WorkflowError) as exc_info:
        await handle.result(timeout=30.0)

    assert "intentional failure" in str(exc_info.value), (
        "WorkflowError message should contain the original exception message"
    )

    # Verify error persisted to DB
    async with AsyncSessionFactory() as session:
        wf_row = await session.get(Workflow, handle.id)
        assert wf_row is not None
        assert wf_row.status == WorkflowStatus.FAILED
        assert wf_row.error is not None
        assert "intentional failure" in wf_row.error


@pytest.mark.asyncio
async def test_workflow_result_timeout(async_db_session):
    """WF-02: handle.result(timeout=0.1) raises TimeoutError if the workflow never completes."""
    handle = await double_workflow.submit(x=9)

    # Do NOT run the worker — workflow stays PENDING
    with pytest.raises(TimeoutError):
        await handle.result(timeout=0.1)


@pytest.mark.asyncio
async def test_workflow_sets_running_status(async_db_session):
    """WF-03: While the worker executes the workflow body, the workflow row status is RUNNING."""
    status_during_execution: list[WorkflowStatus] = []

    @workflow
    async def status_capturing_workflow(x: int) -> dict:
        # Capture this workflow's own status from DB mid-execution using context var
        workflow_id = _active_workflow_id.get()
        async with AsyncSessionFactory() as session:
            wf = await session.get(Workflow, workflow_id)
            if wf:
                status_during_execution.append(wf.status)
        return {"result": x}

    handle = await status_capturing_workflow.submit(x=1)

    worker = AsyncWorker(concurrency=1)
    await worker.run_until_empty()

    assert len(status_during_execution) == 1, "Workflow body must have been executed"
    assert status_during_execution[0] == WorkflowStatus.RUNNING, (
        f"Status during execution should be RUNNING, got {status_during_execution[0]}"
    )
