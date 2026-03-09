"""
API endpoint tests
"""
from app.schemas import JobStatus


def test_health_check(client):
    """Test health endpoint returns OK"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_job(client):
    """Test creating a new job"""
    job_data = {
        "type": "send_email",
        "payload": {"to": "test@example.com"},
        "idempotency_key": "test-key-1",
        "priority": 5
    }

    response = client.post("/jobs", json=job_data)
    assert response.status_code == 200

    data = response.json()
    assert data["type"] == "send_email"
    assert data["status"] == JobStatus.PENDING.value
    assert data["idempotency_key"] == "test-key-1"
    assert data["priority"] == 5
    assert "job_id" in data


def test_create_job_with_default_priority(client):
    """Test that priority defaults to 5 if not provided"""
    job_data = {
        "type": "send_email",
        "payload": {"to": "test@example.com"},
        "idempotency_key": "test-default-priority"
    }

    response = client.post("/jobs", json=job_data)
    assert response.status_code == 200
    assert response.json()["priority"] == 5


def test_idempotency(client):
    """Test that same idempotency key returns same job"""
    job_data = {
        "type": "send_email",
        "payload": {"to": "test@example.com"},
        "idempotency_key": "duplicate-test",
        "priority": 5
    }

    # Create first job
    response1 = client.post("/jobs", json=job_data)
    assert response1.status_code == 200
    job_id_1 = response1.json()["job_id"]

    # Create with same idempotency key
    response2 = client.post("/jobs", json=job_data)
    assert response2.status_code == 200
    job_id_2 = response2.json()["job_id"]

    # Should be the same job
    assert job_id_1 == job_id_2


def test_idempotency_different_payload(client):
    """Test that idempotency works even with different payload"""
    idempotency_key = "same-key"

    # First request
    job_data_1 = {
        "type": "send_email",
        "payload": {"to": "user1@example.com"},
        "idempotency_key": idempotency_key,
        "priority": 5
    }
    response1 = client.post("/jobs", json=job_data_1)
    job1 = response1.json()

    # Second request with different payload but same key
    job_data_2 = {
        "type": "send_email",
        "payload": {"to": "user2@example.com"},  # Different!
        "idempotency_key": idempotency_key,
        "priority": 8  # Different!
    }
    response2 = client.post("/jobs", json=job_data_2)
    job2 = response2.json()

    # Should return original job
    assert job1["job_id"] == job2["job_id"]
    assert job2["payload"]["to"] == "user1@example.com"  # Original payload
    assert job2["priority"] == 5  # Original priority


def test_get_job(client):
    """Test retrieving a job by ID"""
    # Create a job first
    job_data = {
        "type": "send_email",
        "payload": {"to": "test@example.com"},
        "idempotency_key": "get-test",
        "priority": 5
    }
    create_response = client.post("/jobs", json=job_data)
    job_id = create_response.json()["job_id"]

    # Get the job
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["job_id"] == job_id
    assert data["type"] == "send_email"
    assert data["status"] == JobStatus.PENDING.value


def test_get_nonexistent_job(client):
    """Test getting a job that doesn't exist returns 404"""
    response = client.get("/jobs/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_jobs_empty(client):
    """Test listing jobs when database is empty"""
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() == {"jobs": []}


def test_list_jobs(client):
    """Test listing all jobs"""
    # Create multiple jobs
    for i in range(3):
        client.post("/jobs", json={
            "type": "send_email",
            "payload": {"to": f"test{i}@example.com"},
            "idempotency_key": f"list-test-{i}",
            "priority": 5
        })

    # List all jobs
    response = client.get("/jobs")
    assert response.status_code == 200

    data = response.json()
    assert len(data["jobs"]) == 3
    assert all(job["status"] ==
               JobStatus.PENDING.value for job in data["jobs"])


def test_list_jobs_by_status(client):
    """Test filtering jobs by status"""
    # Create a job
    client.post("/jobs", json={
        "type": "send_email",
        "payload": {"to": "test@example.com"},
        "idempotency_key": "status-test",
        "priority": 5
    })

    # Filter by PENDING status
    response = client.get("/jobs?status=PENDING")
    assert response.status_code == 200

    data = response.json()
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["status"] == JobStatus.PENDING.value

    # Filter by COMPLETED status (should be empty)
    response = client.get("/jobs?status=COMPLETED")
    assert response.status_code == 200
    assert len(response.json()["jobs"]) == 0


def test_scheduled_job(client):
    """Test creating a scheduled job"""
    job_data = {
        "type": "send_email",
        "payload": {"to": "test@example.com"},
        "idempotency_key": "scheduled-test",
        "priority": 5,
        "scheduled_at": "2026-12-31T23:59:59"
    }

    response = client.post("/jobs", json=job_data)
    assert response.status_code == 200

    data = response.json()
    assert data["scheduled_at"] is not None
    assert "2026-12-31" in data["scheduled_at"]


def test_admin_stats_empty(client):
    """Test admin stats with empty database"""
    response = client.get("/admin/stats")
    assert response.status_code == 200

    data = response.json()
    assert "status_breakdown" in data
    assert "type_breakdown" in data
    assert data["avg_attempts_for_failed_jobs"] == 0
    assert data["recent_failures"] == []


def test_admin_stats(client):
    """Test admin stats endpoint with data"""
    # Create some jobs
    for i in range(2):
        client.post("/jobs", json={
            "type": "send_email",
            "payload": {"to": f"test{i}@example.com"},
            "idempotency_key": f"stats-test-{i}",
            "priority": 5
        })

    response = client.get("/admin/stats")
    assert response.status_code == 200

    data = response.json()
    assert "status_breakdown" in data
    assert "type_breakdown" in data
    assert data["status_breakdown"]["PENDING"] == 2
    assert data["type_breakdown"]["send_email"] == 2


def test_metrics_endpoint(client):
    """Test that metrics endpoint returns Prometheus format"""
    response = client.get("/metrics")
    assert response.status_code == 200

    # Check it's prometheus format (plain text with specific structure)
    content = response.text
    assert "# HELP" in content or "# TYPE" in content


def test_priority_ordering(client):
    """Test that jobs are created with correct priority"""
    # Create jobs with different priorities
    high_priority = client.post("/jobs", json={
        "type": "send_email",
        "payload": {"to": "high@example.com"},
        "idempotency_key": "high-priority",
        "priority": 1
    }).json()

    low_priority = client.post("/jobs", json={
        "type": "send_email",
        "payload": {"to": "low@example.com"},
        "idempotency_key": "low-priority",
        "priority": 10
    }).json()

    assert high_priority["priority"] == 1
    assert low_priority["priority"] == 10
