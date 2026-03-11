"""
Prometheus metrics for the asyncai application.

The job completion/failure counters are defined in the asyncai library and
re-exported here so application code can import from a single location.
App-specific metrics (creation counter, duration histograms, gauges) are
defined here.
"""
from prometheus_client import Counter, Histogram, Gauge

# Re-export from the library so app code has a single import location.
from asyncai.metrics import jobs_completed_counter, jobs_failed_counter  # noqa: F401

jobs_created_counter = Counter(
    "jobs_created_total",
    "Total number of jobs created via the API",
    ["job_type"],
)

jobs_retried_counter = Counter(
    "jobs_retried_total",
    "Total number of job retry attempts",
    ["job_type"],
)

job_duration_histogram = Histogram(
    "job_duration_seconds",
    "Time spent processing jobs",
    ["job_type"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float("inf")),
)

job_queue_wait_histogram = Histogram(
    "job_queue_wait_seconds",
    "Time jobs spend waiting in the queue before execution",
    ["job_type"],
)

jobs_pending_gauge = Gauge(
    "jobs_pending_count",
    "Current number of jobs in PENDING state",
)

jobs_processing_gauge = Gauge(
    "jobs_processing_count",
    "Current number of jobs in PROCESSING state",
)

worker_up_gauge = Gauge(
    "worker_up",
    "Worker health status (1 = up, 0 = down)",
)
