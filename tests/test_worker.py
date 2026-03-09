"""
Worker logic tests
"""
from unittest.mock import patch
from app.workers import execute_job, handle_send_email, handle_process_data, handle_always_fail
from app.models import Job
from app.schemas import JobStatus
import pytest


def test_handle_send_email_success():
    """Test email handler success case"""
    payload = {"to": "test@example.com"}

    # Mock random to force success (return value > 0.2)
    with patch('app.workers.random.random', return_value=0.5):
        with patch('app.workers.time.sleep'):  # Skip the sleep
            result = handle_send_email(payload)
            assert result["sent_to"] == "test@example.com"
            assert result["status"] == "sent"


def test_handle_send_email_failure():
    """Test email handler failure case"""
    payload = {"to": "test@example.com"}

    # Mock random to force failure (return value < 0.2)
    with patch('app.workers.random.random', return_value=0.1):
        with patch('app.workers.time.sleep'):  # Skip the sleep
            with pytest.raises(Exception, match="Email service temporarily unavailable"):
                handle_send_email(payload)


def test_handle_process_data_success():
    """Test process data handler success"""
    payload = {"data": "test data"}

    with patch('app.workers.random.random', return_value=0.5):
        with patch('app.workers.time.sleep'):
            result = handle_process_data(payload)
            assert result["data"] == "test data"
            assert result["status"] == "processed"


def test_handle_process_data_failure():
    """Test process data handler failure"""
    payload = {"data": "test data"}

    with patch('app.workers.random.random', return_value=0.1):
        with patch('app.workers.time.sleep'):
            with pytest.raises(Exception, match="Process data service temporarily unavailable"):
                handle_process_data(payload)


def test_handle_always_fail():
    """Test that test_failure job type always fails"""
    payload = {"test": "data"}

    with patch('app.workers.time.sleep'):
        with pytest.raises(Exception, match="This job is designed to fail"):
            handle_always_fail(payload)


def test_execute_job_send_email():
    """Test execute_job routes to send_email handler"""
    job = Job(
        idempotency_key="test",
        type="send_email",
        payload={"to": "test@example.com"},
        status=JobStatus.PENDING
    )

    with patch('app.workers.random.random', return_value=0.5):
        with patch('app.workers.time.sleep'):
            result = execute_job(job)
            assert result["sent_to"] == "test@example.com"
            assert result["status"] == "sent"


def test_execute_job_process_data():
    """Test execute_job routes to process_data handler"""
    job = Job(
        idempotency_key="test",
        type="process_data",
        payload={"data": "test"},
        status=JobStatus.PENDING
    )

    with patch('app.workers.random.random', return_value=0.5):
        with patch('app.workers.time.sleep'):
            result = execute_job(job)
            assert result["status"] == "processed"


def test_execute_job_unknown_type():
    """Test that unknown job type raises ValueError"""
    job = Job(
        idempotency_key="test",
        type="unknown_job_type",
        payload={},
        status=JobStatus.PENDING
    )

    with pytest.raises(ValueError, match="Unknown job type: unknown_job_type"):
        execute_job(job)


def test_execute_job_test_failure():
    """Test that test_failure type always raises exception"""
    job = Job(
        idempotency_key="test",
        type="test_failure",
        payload={},
        status=JobStatus.PENDING
    )

    with patch('app.workers.time.sleep'):
        with pytest.raises(Exception, match="This job is designed to fail"):
            execute_job(job)
