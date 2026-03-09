"""
SQLAlchemy Table Models
"""
from typing import Optional, Dict
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Enum, JSON, func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from app.db import Base
from app.schemas import JobStatus


class Job(Base): # pylint: disable=too-few-public-methods
    """Job"""
    __tablename__ = "job"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"),
        nullable=False,
        default=JobStatus.PENDING,
    )

    payload: Mapped[Dict] = mapped_column(
        JSON,
        nullable=False,
    )

    result: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(), # pylint: disable=not-callable
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(), # pylint: disable=not-callable
        onupdate=func.now(), # pylint: disable=not-callable
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False
    )

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
