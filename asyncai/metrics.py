"""
Prometheus metrics for the asyncai worker.

Defined in the asyncai package so the worker can record telemetry without
depending on any application layer. Import these in application code if you
want job completion/failure counters in a shared metrics namespace.
"""
from prometheus_client import Counter

jobs_completed_counter = Counter(
    "asyncai_jobs_completed_total",
    "Total number of asyncai jobs completed successfully",
    ["job_type"],
)

jobs_failed_counter = Counter(
    "asyncai_jobs_failed_total",
    "Total number of asyncai jobs that permanently failed (retries exhausted)",
    ["job_type"],
)

__all__ = ["jobs_completed_counter", "jobs_failed_counter"]
