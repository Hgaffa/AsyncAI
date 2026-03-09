"""Fast API Server"""
from typing import Optional
import datetime

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import Response

from sqlalchemy.orm import Session
from sqlalchemy import func

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.schemas import JobCreateRequest, JobResponse, JobStatus, JobListResponse
from app.db import get_db
from app.models import Job
from app.utils import build_job_response
from app.metrics import jobs_created_counter

app = FastAPI()


@app.get("/health")
def health():
    """Health check endpoint to verify service is running"""
    return {"status": "ok"}


@app.post("/jobs", response_model=JobResponse)
def create_job(
        job_request: JobCreateRequest,
        db: Session = Depends(get_db)):
    """
    Create a new job with idempotency support.

    If a job with the same idempotency_key already exists, 
    returns that job instead of creating a new one.

    This ensures that retrying the same request doesn't create
    duplicate jobs.
    """

    # Check if job with this idempotency key exists
    existing_job = db.query(Job).filter(
        Job.idempotency_key == job_request.idempotency_key
    ).first()

    if existing_job:
        # Return existing job
        return build_job_response(existing_job)

    # Otherwise, create a new job
    current_time = datetime.datetime.now()

    # Parse scheduled_at if provided
    scheduled_at_datetime = None
    if job_request.scheduled_at:
        try:
            # Parse ISO format datetime string
            scheduled_at_datetime = datetime.datetime.fromisoformat(
                job_request.scheduled_at.replace('Z', '+00:00')
            )
        except (ValueError, AttributeError) as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid scheduled_at format. "
                    "Use ISO 8601 format (e.g., 2026-01-30T15:00:00)"
                )
            ) from exc

    new_job = Job(
        idempotency_key=job_request.idempotency_key,
        type=job_request.type,
        payload=job_request.payload,
        status=JobStatus.PENDING,
        priority=job_request.priority,
        scheduled_at=scheduled_at_datetime,
        attempts=0,
        max_attempts=3,
        created_at=current_time,
        updated_at=current_time
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)  # Gets a new auto-generated ID

    # Record metrics
    jobs_created_counter.labels(job_type=new_job.type).inc()

    return build_job_response(new_job)


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Get the status and details of a specific job by ID.
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return build_job_response(job)


@app.get("/jobs", response_model=JobListResponse)
# Status is an optional query parameter as opposed to a URL parameter
def get_jobs(
        status: Optional[JobStatus] = None,
        db: Session = Depends(get_db)):
    """
    List all jobs, optionally filtered by status.

    Query parameters:
    - status: Filter jobs by status (PENDING, PROCESSING, COMPLETED, FAILED)
    """
    query = db.query(Job)

    if status is not None:
        query = query.filter(Job.status == status)

    jobs = query.all()

    # Conver to response format
    job_list = [build_job_response(job) for job in jobs]

    return JobListResponse(jobs=job_list)


@app.get("/metrics")
def metrics():
    """
    Prometheus Metrics Endpoint
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/admin/stats")
def get_stats(db: Session = Depends(get_db)):
    """Admin endpoint showing system statistics"""

    # Get counts by status
    status_counts = db.query(
        Job.status,
        func.count(Job.id).label('count')  # pylint: disable=not-callable
    ).group_by(Job.status).all()

    # Get counts by type
    type_counts = db.query(
        Job.type,
        func.count(Job.id).label('count')  # pylint: disable=not-callable
    ).group_by(Job.type).all()

    # Get average attempts for failed jobs
    avg_attempts = db.query(
        func.avg(Job.attempts)
    ).filter(Job.status == JobStatus.FAILED).scalar()

    # Recent failed jobs
    recent_failures = db.query(Job).filter(
        Job.status == JobStatus.FAILED
    ).order_by(Job.updated_at.desc()).limit(10).all()

    return {
        "status_breakdown": {
            status.value: count for status, count in status_counts
        },
        "type_breakdown": dict(type_counts),
        "avg_attempts_for_failed_jobs": float(avg_attempts) if avg_attempts else 0,
        "recent_failures": [
            {
                "job_id": job.id,
                "type": job.type,
                "error": job.error_message,
                "attempts": job.attempts,
                "failed_at": job.finished_at.isoformat() if job.finished_at else None
            }
            for job in recent_failures
        ]
    }
