"""
Pydantic request/response schemas for the asyncai REST API.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    """Valid states for a job throughout its lifecycle."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobCreateRequest(BaseModel):
    """Payload for creating a new job via ``POST /jobs``."""

    type: str
    idempotency_key: str
    payload: Dict[str, Any]
    priority: int = 5
    scheduled_at: Optional[datetime] = None


class JobResponse(BaseModel):
    """Full representation of a job returned by the API."""

    job_id: int
    type: str
    idempotency_key: str
    status: JobStatus
    priority: int
    payload: Dict[str, Any]
    created_at: str
    updated_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    scheduled_at: Optional[str]
    error_message: Optional[str]
    attempts: int
    result: Optional[Any] = None


class JobListResponse(BaseModel):
    """Wrapper for a list of job responses."""

    jobs: List[JobResponse]
