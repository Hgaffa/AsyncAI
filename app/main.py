"""FastAPI application for the asyncai job management API."""
import datetime

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.metrics import jobs_created_counter
from app.models import Job
from app.schemas import JobCreateRequest, JobListResponse, JobResponse, JobStatus
from app.utils import build_job_response

app = FastAPI()


@app.get("/health")
def health():
    """Health check endpoint — returns 200 OK when the service is running."""
    return {"status": "ok"}


@app.post("/jobs", response_model=JobResponse)
def create_job(job_request: JobCreateRequest, db: Session = Depends(get_db)):
    """Create a new job with idempotency support.

    If a job with the same ``idempotency_key`` already exists, that job is
    returned unchanged.  This guarantees that retrying the same request never
    produces duplicate jobs.
    """
    existing_job = db.query(Job).filter(
        Job.idempotency_key == job_request.idempotency_key
    ).first()
    if existing_job:
        return build_job_response(existing_job)

    new_job = Job(
        idempotency_key=job_request.idempotency_key,
        type=job_request.type,
        payload=job_request.payload,
        status=JobStatus.PENDING,
        priority=job_request.priority,
        scheduled_at=job_request.scheduled_at,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    jobs_created_counter.labels(job_type=new_job.type).inc()
    return build_job_response(new_job)


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Return the status and details of a specific job by ID."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return build_job_response(job)


@app.get("/jobs", response_model=JobListResponse)
def get_jobs(status: JobStatus = None, db: Session = Depends(get_db)):
    """List all jobs, optionally filtered by status.

    Query parameters:
        status: Filter by PENDING, PROCESSING, COMPLETED, or FAILED.
    """
    query = db.query(Job)
    if status is not None:
        query = query.filter(Job.status == status)
    return JobListResponse(jobs=[build_job_response(job) for job in query.all()])


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/stats")
def get_stats(db: Session = Depends(get_db)):
    """Admin endpoint showing system statistics."""
    status_counts = db.query(
        Job.status,
        func.count(Job.id).label("count"),  # pylint: disable=not-callable
    ).group_by(Job.status).all()

    type_counts = db.query(
        Job.type,
        func.count(Job.id).label("count"),  # pylint: disable=not-callable
    ).group_by(Job.type).all()

    avg_attempts = db.query(func.avg(Job.attempts)).filter(
        Job.status == JobStatus.FAILED
    ).scalar()

    recent_failures = (
        db.query(Job)
        .filter(Job.status == JobStatus.FAILED)
        .order_by(Job.updated_at.desc())
        .limit(10)
        .all()
    )

    return {
        "status_breakdown": {status.value: count for status, count in status_counts},
        "type_breakdown": dict(type_counts),
        "avg_attempts_for_failed_jobs": float(avg_attempts) if avg_attempts else 0,
        "recent_failures": [
            {
                "job_id": job.id,
                "type": job.type,
                "error": job.error_message,
                "attempts": job.attempts,
                "failed_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in recent_failures
        ],
    }
