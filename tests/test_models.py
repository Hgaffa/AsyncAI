"""
Database model tests
"""
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.models import Job
from app.schemas import JobStatus
import pytest


def test_create_job(db_session):
    """Test creating a job in database"""
    job = Job(
        idempotency_key="test-key",
        type="send_email",
        payload={"to": "test@example.com"},
        status=JobStatus.PENDING,
        priority=5
    )

    db_session.add(job)
    db_session.commit()

    assert job.id is not None
    assert job.idempotency_key == "test-key"
    assert job.status == JobStatus.PENDING
    assert job.type == "send_email"
    assert job.priority == 5


def test_job_defaults(db_session):
    """Test that job has correct default values"""
    job = Job(
        idempotency_key="test-defaults",
        type="send_email",
        payload={"to": "test@example.com"},
        status=JobStatus.PENDING
    )

    db_session.add(job)
    db_session.commit()

    # Check defaults
    assert job.attempts == 0
    assert job.max_attempts == 3
    assert job.priority == 5
    assert job.created_at is not None
    assert job.updated_at is not None
    assert job.result is None
    assert job.error_message is None


def test_idempotency_key_unique(db_session):
    """Test that idempotency key must be unique"""
    job1 = Job(
        idempotency_key="duplicate",
        type="send_email",
        payload={},
        status=JobStatus.PENDING
    )
    db_session.add(job1)
    db_session.commit()

    # Try to create another job with same idempotency key
    job2 = Job(
        idempotency_key="duplicate",
        type="send_email",
        payload={},
        status=JobStatus.PENDING
    )
    db_session.add(job2)

    # Should raise integrity error
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_job_status_enum(db_session):
    """Test all job status values"""
    statuses = [JobStatus.PENDING, JobStatus.PROCESSING,
                JobStatus.COMPLETED, JobStatus.FAILED]

    for i, status in enumerate(statuses):
        job = Job(
            idempotency_key=f"status-test-{i}",
            type="send_email",
            payload={},
            status=status
        )
        db_session.add(job)

    db_session.commit()

    # Query back and verify
    jobs = db_session.query(Job).all()
    assert len(jobs) == 4
    assert set(job.status for job in jobs) == set(statuses)


def test_job_timestamps(db_session):
    """Test that timestamps are set correctly"""
    job = Job(
        idempotency_key="timestamp-test",
        type="send_email",
        payload={},
        status=JobStatus.PENDING
    )

    db_session.add(job)
    db_session.commit()

    # Check timestamps exist
    assert job.created_at is not None
    assert job.updated_at is not None
    assert job.started_at is None
    assert job.finished_at is None

    # Update the job
    original_created_at = job.created_at
    job.status = JobStatus.COMPLETED
    job.finished_at = datetime.now()
    db_session.commit()

    # created_at should not change
    assert job.created_at == original_created_at
    # finished_at should now be set
    assert job.finished_at is not None


def test_job_with_result(db_session):
    """Test storing result in job"""
    job = Job(
        idempotency_key="result-test",
        type="send_email",
        payload={"to": "test@example.com"},
        status=JobStatus.COMPLETED,
        result={"message": "Email sent successfully", "id": 12345}
    )

    db_session.add(job)
    db_session.commit()

    # Query back
    retrieved_job = db_session.query(Job).filter_by(
        idempotency_key="result-test").first()
    assert retrieved_job.result == {
        "message": "Email sent successfully", "id": 12345}


def test_job_with_error(db_session):
    """Test storing error message in job"""
    error_msg = "Connection timeout after 30 seconds"
    job = Job(
        idempotency_key="error-test",
        type="send_email",
        payload={},
        status=JobStatus.FAILED,
        error_message=error_msg,
        attempts=3
    )

    db_session.add(job)
    db_session.commit()

    # Query back
    retrieved_job = db_session.query(Job).filter_by(
        idempotency_key="error-test").first()
    assert retrieved_job.error_message == error_msg
    assert retrieved_job.attempts == 3


def test_job_scheduled_at(db_session):
    """Test scheduled_at field"""
    scheduled_time = datetime(2026, 12, 31, 23, 59, 59)
    job = Job(
        idempotency_key="scheduled-test",
        type="send_email",
        payload={},
        status=JobStatus.PENDING,
        scheduled_at=scheduled_time
    )

    db_session.add(job)
    db_session.commit()

    # Query back
    retrieved_job = db_session.query(Job).filter_by(
        idempotency_key="scheduled-test").first()
    assert retrieved_job.scheduled_at.year == 2026
    assert retrieved_job.scheduled_at.month == 12
    assert retrieved_job.scheduled_at.day == 31


def test_query_by_status(db_session):
    """Test querying jobs by status"""
    # Create jobs with different statuses
    statuses = [
        JobStatus.PENDING,
        JobStatus.PENDING,
        JobStatus.PROCESSING,
        JobStatus.COMPLETED,
        JobStatus.FAILED
    ]

    for i, status in enumerate(statuses):
        job = Job(
            idempotency_key=f"query-test-{i}",
            type="send_email",
            payload={},
            status=status
        )
        db_session.add(job)

    db_session.commit()

    # Query PENDING jobs
    pending_jobs = db_session.query(Job).filter(
        Job.status == JobStatus.PENDING).all()
    assert len(pending_jobs) == 2

    # Query COMPLETED jobs
    completed_jobs = db_session.query(Job).filter(
        Job.status == JobStatus.COMPLETED).all()
    assert len(completed_jobs) == 1


def test_query_by_priority(db_session):
    """Test querying jobs by priority"""
    # Create jobs with different priorities
    for priority in [1, 5, 10]:
        job = Job(
            idempotency_key=f"priority-{priority}",
            type="send_email",
            payload={},
            status=JobStatus.PENDING,
            priority=priority
        )
        db_session.add(job)

    db_session.commit()

    # Query high priority jobs
    high_priority = db_session.query(Job).filter(Job.priority <= 3).all()
    assert len(high_priority) == 1
    assert high_priority[0].priority == 1
