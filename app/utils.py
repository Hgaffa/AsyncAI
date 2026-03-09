"""
Utility functions for processing and formatting job data
"""
from app.schemas import JobResponse
from app.models import Job


def build_job_response(job: Job) -> JobResponse:
    """
    Convert a SQLAlchemy Job model instance to a JobResponse Pydantic model.

    Args:
        job: SQLAlchemy Job model instance

    Returns:
        JobResponse: Pydantic model for API response
    """
    return JobResponse(
        job_id=job.id,
        idempotency_key=job.idempotency_key,
        type=job.type,
        status=job.status,
        priority=job.priority,
        payload=job.payload,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        scheduled_at=job.scheduled_at.isoformat() if job.scheduled_at else None,
        error_message=job.error_message,
        attempts=job.attempts,
        result=job.result,
    )
