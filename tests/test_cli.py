"""
Tests for the asyncai CLI.

Plan 04-01 scaffold: 5 tests in RED state until Task 2 (cli.py implementation).
Tests test_db_migrate, test_worker_start, and test_dotenv_loaded turn GREEN in
Plan 04-01.  test_workflows_list and test_workflow_inspect remain RED until
Plan 04-02 implements those commands.

Plan 05-02 additions: targeted tests for previously uncovered branches to
reach 85%+ overall coverage on asyncai/ modules.
"""
import asyncio
import uuid
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from asyncai.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# CLI-01: asyncai db migrate
# ---------------------------------------------------------------------------


def test_db_migrate(monkeypatch):
    """asyncai db migrate should call alembic upgrade and print confirmation."""
    monkeypatch.setattr("alembic.command.upgrade", lambda cfg, rev: None)

    result = runner.invoke(app, ["db", "migrate"])

    assert result.exit_code == 0, result.output
    assert "Migrations applied" in result.output


# ---------------------------------------------------------------------------
# CLI-02: asyncai worker start
# ---------------------------------------------------------------------------


def test_worker_start(monkeypatch):
    """asyncai worker start should import the module and enter the worker loop."""
    import importlib

    monkeypatch.setattr(importlib, "import_module", lambda name: None)

    # Replace _run_worker with a coroutine that returns immediately.
    async def _noop_worker(concurrency: int) -> None:
        return

    monkeypatch.setattr("asyncai.cli._run_worker", _noop_worker)

    result = runner.invoke(app, ["worker", "start", "--app", "mymodule", "--concurrency", "2"])

    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# CLI-03: asyncai workflows  (Plan 02)
# ---------------------------------------------------------------------------


def test_workflows_list(monkeypatch):
    """asyncai workflows should list workflow rows (Plan 02 — RED for Plan 01)."""
    monkeypatch.setattr("asyncai.cli._fetch_workflows", lambda limit: [])

    result = runner.invoke(app, ["workflows"])

    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# CLI-04: asyncai workflow <uuid>  (Plan 02)
# ---------------------------------------------------------------------------


def test_workflow_inspect(monkeypatch):
    """asyncai workflow <uuid> should exit non-zero when the workflow is not found."""
    monkeypatch.setattr("asyncai.cli._fetch_workflow_detail", lambda wid: (None, []))

    result = runner.invoke(app, ["workflow", "some-uuid"])

    assert result.exit_code != 0, result.output


# ---------------------------------------------------------------------------
# CLI-05: .env support
# ---------------------------------------------------------------------------


def test_dotenv_loaded():
    """Importing asyncai.cli must not raise even when ASYNCAI_DB_URL is unset."""
    # The import already happened at module load (above). Verify --help works.
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# CLI-06: asyncai jobs (list)
# ---------------------------------------------------------------------------


def test_jobs_list(monkeypatch):
    """asyncai jobs should list standalone job rows (exit 0 with empty list)."""
    monkeypatch.setattr("asyncai.cli._fetch_jobs", lambda limit: [])

    result = runner.invoke(app, ["jobs"])

    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# CLI-06: asyncai job <id> (inspect)
# ---------------------------------------------------------------------------


def test_job_inspect_not_found(monkeypatch):
    """asyncai job <id> should exit non-zero when the job is not found."""
    monkeypatch.setattr("asyncai.cli._fetch_job_detail", lambda job_id: None)

    result = runner.invoke(app, ["job", "999"])

    assert result.exit_code != 0, result.output


# ---------------------------------------------------------------------------
# Additional coverage tests (Plan 05-02)
# ---------------------------------------------------------------------------


def test_db_migrate_exception(monkeypatch):
    """asyncai db migrate should print the error and exit non-zero on failure."""
    def raise_error(cfg, rev):
        raise RuntimeError("DB connection refused")

    monkeypatch.setattr("alembic.command.upgrade", raise_error)

    result = runner.invoke(app, ["db", "migrate"])

    assert result.exit_code != 0, result.output
    assert "DB connection refused" in result.output


def test_worker_start_keyboard_interrupt(monkeypatch):
    """asyncai worker start should print 'Worker stopped.' on KeyboardInterrupt."""
    import importlib

    monkeypatch.setattr(importlib, "import_module", lambda name: None)

    async def _interrupt_worker(concurrency: int) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("asyncai.cli._run_worker", _interrupt_worker)

    result = runner.invoke(app, ["worker", "start", "--app", "mymodule"])

    assert result.exit_code == 0, result.output
    assert "Worker stopped" in result.output


def test_workflows_list_with_data(monkeypatch):
    """asyncai workflows renders table rows when workflows are returned."""
    from asyncai.db.models import WorkflowStatus
    import datetime

    wf = MagicMock()
    wf.id = uuid.uuid4()
    wf.status = MagicMock()
    wf.status.value = "COMPLETED"
    wf.created_at = datetime.datetime(2026, 1, 1, 12, 0, 0)
    wf.result = {"result": 42}
    wf.error = None

    monkeypatch.setattr("asyncai.cli._fetch_workflows", lambda limit: [wf])

    result = runner.invoke(app, ["workflows"])

    assert result.exit_code == 0, result.output
    assert "COMPLETED" in result.output


def test_workflow_inspect_found_with_steps(monkeypatch):
    """asyncai workflow <uuid> should display workflow and step timeline when found."""
    import datetime

    wf = MagicMock()
    wf.id = uuid.uuid4()
    wf.status = MagicMock()
    wf.status.value = "COMPLETED"
    wf.created_at = datetime.datetime(2026, 1, 1, 12, 0, 0)
    wf.result = {"value": 10}
    wf.error = None

    step = MagicMock()
    step.step_name = "step1"
    step.status = MagicMock()
    step.status.value = "COMPLETED"
    step.created_at = datetime.datetime(2026, 1, 1, 12, 0, 1)

    monkeypatch.setattr("asyncai.cli._fetch_workflow_detail", lambda wid: (wf, [step]))

    result = runner.invoke(app, ["workflow", str(uuid.uuid4())])

    assert result.exit_code == 0, result.output
    assert "COMPLETED" in result.output
    assert "step1" in result.output


def test_workflow_inspect_found_no_steps(monkeypatch):
    """asyncai workflow <uuid> should display workflow info when no steps exist."""
    import datetime

    wf = MagicMock()
    wf.id = uuid.uuid4()
    wf.status = MagicMock()
    wf.status.value = "PENDING"
    wf.created_at = datetime.datetime(2026, 1, 1, 12, 0, 0)
    wf.result = None
    wf.error = "something went wrong"

    monkeypatch.setattr("asyncai.cli._fetch_workflow_detail", lambda wid: (wf, []))

    result = runner.invoke(app, ["workflow", str(uuid.uuid4())])

    assert result.exit_code == 0, result.output
    assert "something went wrong" in result.output


def test_workflow_inspect_invalid_uuid():
    """asyncai workflow with a non-UUID string should exit non-zero."""
    result = runner.invoke(app, ["workflow", "not-a-valid-uuid"])

    assert result.exit_code != 0, result.output


def test_jobs_list_with_data(monkeypatch):
    """asyncai jobs renders table rows when jobs are returned."""
    import datetime
    from asyncai.db.models import JobStatus

    job = MagicMock()
    job.id = 42
    job.type = "my_task"
    job.status = MagicMock()
    job.status.value = "COMPLETED"
    job.attempts = 1
    job.created_at = datetime.datetime(2026, 1, 1, 12, 0, 0)
    job.result = {"result": 99}
    job.error_message = None

    monkeypatch.setattr("asyncai.cli._fetch_jobs", lambda limit: [job])

    result = runner.invoke(app, ["jobs"])

    assert result.exit_code == 0, result.output
    assert "my_task" in result.output
    assert "COMPLETED" in result.output


def test_jobs_list_with_error_message(monkeypatch):
    """asyncai jobs shows error_message in summary when result is None."""
    import datetime

    job = MagicMock()
    job.id = 7
    job.type = "broken_task"
    job.status = MagicMock()
    job.status.value = "FAILED"
    job.attempts = 3
    job.created_at = datetime.datetime(2026, 1, 1, 12, 0, 0)
    job.result = None
    job.error_message = "something went wrong"

    monkeypatch.setattr("asyncai.cli._fetch_jobs", lambda limit: [job])

    result = runner.invoke(app, ["jobs"])

    assert result.exit_code == 0, result.output
    # Rich may wrap "something went wrong" across table cell rows; check partial match
    assert "something went" in result.output


def test_job_inspect_found(monkeypatch):
    """asyncai job <id> displays job details when job is found."""
    import datetime

    job = MagicMock()
    job.id = 5
    job.type = "my_task"
    job.status = MagicMock()
    job.status.value = "COMPLETED"
    job.attempts = 1
    job.max_attempts = 3
    job.created_at = datetime.datetime(2026, 1, 1, 12, 0, 0)
    job.started_at = datetime.datetime(2026, 1, 1, 12, 0, 1)
    job.finished_at = datetime.datetime(2026, 1, 1, 12, 0, 2)
    job.payload = {"x": 1}
    job.result = {"result": 2}
    job.error_message = None

    monkeypatch.setattr("asyncai.cli._fetch_job_detail", lambda job_id: job)

    result = runner.invoke(app, ["job", "5"])

    assert result.exit_code == 0, result.output
    assert "my_task" in result.output
    assert "COMPLETED" in result.output


def test_job_inspect_found_with_error(monkeypatch):
    """asyncai job <id> displays error_message when job failed."""
    import datetime

    job = MagicMock()
    job.id = 8
    job.type = "fail_task"
    job.status = MagicMock()
    job.status.value = "FAILED"
    job.attempts = 3
    job.max_attempts = 3
    job.created_at = datetime.datetime(2026, 1, 1, 12, 0, 0)
    job.started_at = datetime.datetime(2026, 1, 1, 12, 0, 1)
    job.finished_at = datetime.datetime(2026, 1, 1, 12, 0, 2)
    job.payload = {"x": 99}
    job.result = None
    job.error_message = "task failed badly"

    monkeypatch.setattr("asyncai.cli._fetch_job_detail", lambda job_id: job)

    result = runner.invoke(app, ["job", "8"])

    assert result.exit_code == 0, result.output
    assert "task failed badly" in result.output
