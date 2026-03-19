"""
asyncai CLI — command-line interface for database management and worker control.

ASYNCAI_DB_URL is loaded from a .env file by asyncai.db.session at import time.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import typer
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from rich.console import Console
from rich.table import Table

# Importing asyncai.db.session triggers load_dotenv() at module level.
from asyncai.db.session import AsyncSessionFactory  # noqa: F401

# ---------------------------------------------------------------------------
# App structure
# ---------------------------------------------------------------------------

app = typer.Typer(no_args_is_help=True)
db_app = typer.Typer(no_args_is_help=True, help="Database management commands.")
worker_app = typer.Typer(no_args_is_help=True, help="Worker management commands.")

app.add_typer(db_app, name="db")
app.add_typer(worker_app, name="worker")


# ---------------------------------------------------------------------------
# asyncai db migrate
# ---------------------------------------------------------------------------


@db_app.command()
def migrate() -> None:
    """Apply all pending Alembic migrations to head."""
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    try:
        alembic_command.upgrade(AlembicConfig(str(ini_path)), "head")
        typer.echo("Migrations applied to head.")
    except Exception as e:  # noqa: BLE001
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# asyncai worker start
# ---------------------------------------------------------------------------


async def _run_worker(concurrency: int) -> None:
    """Internal async loop: crash-recover then poll the job queue indefinitely."""
    from asyncai.worker import AsyncWorker, recover_crashed_jobs

    async with AsyncSessionFactory() as session:
        async with session.begin():
            await recover_crashed_jobs(session)
    worker = AsyncWorker(concurrency=concurrency)
    while True:
        await worker.run_until_empty()
        await asyncio.sleep(1.0)


@worker_app.command()
def start(
    app_module: str = typer.Option(..., "--app", help="Python module to import (registers @task decorators)."),
    concurrency: int = typer.Option(10, "--concurrency", help="Maximum concurrent jobs."),
) -> None:
    """Import an application module and start the async job worker."""
    # Prepend CWD so the user module is resolvable without install.
    sys.path.insert(0, os.getcwd())
    importlib.import_module(app_module)
    typer.echo(f"Starting worker. module={app_module} concurrency={concurrency}")
    try:
        asyncio.run(_run_worker(concurrency))
    except KeyboardInterrupt:
        typer.echo("Worker stopped.")


# ---------------------------------------------------------------------------
# asyncai workflows (list)
# ---------------------------------------------------------------------------


def _fetch_workflows(limit: int) -> list[Any]:
    """Return a list of recent Workflow rows ordered by created_at desc."""

    async def _query() -> list[Any]:
        from sqlalchemy import select
        from asyncai.db.models import Workflow

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(Workflow).order_by(Workflow.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())

    return asyncio.run(_query())


@app.command("workflows")
def workflows_list(
    limit: int = typer.Option(20, "--limit", help="Max rows to display"),
) -> None:
    """List recent workflows."""
    rows = _fetch_workflows(limit)
    console = Console()
    table = Table(title="Recent Workflows", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Created At")
    table.add_column("Result Summary")
    for wf in rows:
        summary = str(wf.result)[:60] if wf.result else (wf.error[:60] if wf.error else "\u2014")
        table.add_row(str(wf.id), wf.status.value, str(wf.created_at), summary)
    console.print(table)


# ---------------------------------------------------------------------------
# asyncai workflow <id> (inspect)
# ---------------------------------------------------------------------------


def _fetch_workflow_detail(wid: uuid.UUID) -> tuple[Any, ...]:
    """Return (Workflow | None, list[WorkflowStep]) for the given workflow UUID."""

    async def _query() -> tuple[Any, ...]:
        from sqlalchemy import select
        from asyncai.db.models import Workflow, WorkflowStep

        async with AsyncSessionFactory() as session:
            wf = await session.get(Workflow, wid)
            if wf is None:
                return None, []
            result = await session.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_id == wid)
                .order_by(WorkflowStep.created_at.asc())
            )
            steps = list(result.scalars().all())
            return wf, steps

    return asyncio.run(_query())


@app.command("workflow")
def workflow_inspect(
    workflow_id: str = typer.Argument(..., help="Workflow UUID to inspect."),
) -> None:
    """Inspect a specific workflow and its step timeline."""
    try:
        wid = uuid.UUID(workflow_id)
    except ValueError:
        typer.echo(f"Invalid UUID: {workflow_id}", err=True)
        raise typer.Exit(code=1)
    wf, steps = _fetch_workflow_detail(wid)
    if wf is None:
        typer.echo(f"Workflow {workflow_id} not found.", err=True)
        raise typer.Exit(code=1)
    console = Console()
    console.print(f"[bold]Workflow:[/bold] {wf.id}")
    console.print(f"[bold]Status:[/bold]   {wf.status.value}")
    console.print(f"[bold]Created:[/bold]  {wf.created_at}")
    if wf.result is not None:
        console.print(f"[bold]Result:[/bold]   {wf.result}")
    if wf.error is not None:
        console.print(f"[bold]Error:[/bold]    {wf.error}")
    if steps:
        step_table = Table(title="Step Timeline")
        step_table.add_column("Step Name")
        step_table.add_column("Status", style="magenta")
        step_table.add_column("Created At")
        for step in steps:
            step_table.add_row(step.step_name, step.status.value, str(step.created_at))
        console.print(step_table)


# ---------------------------------------------------------------------------
# asyncai jobs (list)
# ---------------------------------------------------------------------------


def _fetch_jobs(limit: int) -> list[Any]:
    """Return a list of recent standalone Job rows (no workflow_id) ordered by created_at desc."""

    async def _query() -> list[Any]:
        from sqlalchemy import select
        from asyncai.db.models import Job

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(Job)
                .where(Job.workflow_id.is_(None))
                .order_by(Job.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    return asyncio.run(_query())


def _fetch_job_detail(job_id: int) -> Any:
    """Return a single Job row by id, or None if not found."""

    async def _query() -> Any:
        from asyncai.db.models import Job

        async with AsyncSessionFactory() as session:
            return await session.get(Job, job_id)

    return asyncio.run(_query())


@app.command("jobs")
def jobs_list(
    limit: int = typer.Option(20, "--limit", help="Max rows to display"),
) -> None:
    """List recent standalone task jobs (no workflow context)."""
    rows = _fetch_jobs(limit)
    console = Console()
    table = Table(title="Recent Jobs", show_lines=False)
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("Status", style="magenta")
    table.add_column("Attempts")
    table.add_column("Created At")
    table.add_column("Result Summary")
    for job in rows:
        summary = (
            str(job.result)[:60]
            if job.result
            else (job.error_message[:60] if job.error_message else "\u2014")
        )
        table.add_row(
            str(job.id),
            job.type,
            job.status.value,
            str(job.attempts),
            str(job.created_at),
            summary,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# asyncai job <id> (inspect)
# ---------------------------------------------------------------------------


@app.command("job")
def job_inspect(
    job_id: int = typer.Argument(..., help="Job ID to inspect."),
) -> None:
    """Inspect a specific standalone task job by ID."""
    job = _fetch_job_detail(job_id)
    if job is None:
        typer.echo(f"Job {job_id} not found.", err=True)
        raise typer.Exit(code=1)
    console = Console()
    console.print(f"[bold]Job:[/bold]      {job.id}")
    console.print(f"[bold]Type:[/bold]     {job.type}")
    console.print(f"[bold]Status:[/bold]   {job.status.value}")
    console.print(f"[bold]Attempts:[/bold] {job.attempts}/{job.max_attempts}")
    console.print(f"[bold]Created:[/bold]  {job.created_at}")
    console.print(f"[bold]Started:[/bold]  {job.started_at}")
    console.print(f"[bold]Finished:[/bold] {job.finished_at}")
    console.print(f"[bold]Payload:[/bold]  {job.payload}")
    if job.result is not None:
        console.print(f"[bold]Result:[/bold]   {job.result}")
    if job.error_message is not None:
        console.print(f"[bold]Error:[/bold]    {job.error_message}")


__all__ = ["app", "_fetch_jobs", "_fetch_job_detail"]
