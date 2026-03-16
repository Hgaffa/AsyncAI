"""
Tests for the asyncai CLI.

Plan 04-01 scaffold: 5 tests in RED state until Task 2 (cli.py implementation).
Tests test_db_migrate, test_worker_start, and test_dotenv_loaded turn GREEN in
Plan 04-01.  test_workflows_list and test_workflow_inspect remain RED until
Plan 04-02 implements those commands.
"""
import asyncio

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
