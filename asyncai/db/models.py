"""
SQLAlchemy ORM model classes for asyncai.

Exports:
    Base: DeclarativeBase subclass (used by Alembic env.py for target_metadata)
    JobStatus, WorkflowStatus, StepStatus: Python enums
    Job, Workflow, WorkflowStep, TaskResult: mapped ORM classes
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class JobStatus(str, PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowStatus(str, PyEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StepStatus(str, PyEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Single authoritative Base for all asyncai models.
    Alembic env.py imports this to build target_metadata.
    """
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Job(Base):
    """Mirrors the existing PostgreSQL table.

    CRITICAL: job_status enum already exists in PostgreSQL, so
    Enum(..., create_type=False) must be used to avoid a CREATE TYPE clash
    during migrations.
    """
    __tablename__ = "job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[Optional[JobStatus]] = mapped_column(
        Enum(JobStatus, name="job_status", create_type=False),
        nullable=True,
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # New columns added by Plan 03 migration
    workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
    )
    step_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # No relationship() attrs in Phase 1 -- avoids MissingGreenlet risk
    # (lazy loading not supported in async context; add explicitly in Phase 2)


class Workflow(Base):
    """Persistent workflow instance."""
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status"),
        nullable=False,
        default=WorkflowStatus.PENDING,
    )
    context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorkflowStep(Base):
    """Individual step within a Workflow."""
    __tablename__ = "workflow_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus, name="step_status"),
        nullable=False,
        default=StepStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TaskResult(Base):
    """Cached result for a completed task job."""
    __tablename__ = "task_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


__all__ = [
    "Base",
    "JobStatus",
    "WorkflowStatus",
    "StepStatus",
    "Job",
    "Workflow",
    "WorkflowStep",
    "TaskResult",
]
