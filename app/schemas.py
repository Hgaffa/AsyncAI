"""
Pydantic Models
"""
from typing import Any, Optional, Dict, List
from enum import Enum
from pydantic import BaseModel

class JobStatus(str, Enum):
    """Job Status Model"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobCreateRequest(BaseModel):
    """Job Create Request Model"""
    type: str
    idempotency_key: str
    payload: Dict[str, Any]
    priority: Optional[int] = 5
    scheduled_at: Optional[str] = None


class JobResponse(BaseModel):
    """Job Response Model"""
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
    """Job List Response Model"""
    jobs: List[JobResponse]
