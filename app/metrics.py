'''
Prometheus metrics configuration
'''
from prometheus_client import Counter, Histogram, Gauge

# Counters - always increase
jobs_created_counter = Counter(
    'jobs_created_total',
    'Total number of jobs created',
    ['job_type']  # Label to track by job type
)

jobs_completed_counter = Counter(
    'jobs_completed_total',
    'Total number of jobs completed successfully',
    ['job_type']
)

jobs_failed_counter = Counter(
    'jobs_failed_total',
    'Total number of jobs failed permanently',
    ['job_type']
)

jobs_retried_counter = Counter(
    'jobs_retried_total',
    'Total number of job retry attempts',
    ['job_type']
)

# Histograms - measure distributions
job_duration_histogram = Histogram(
    'job_duration_seconds',
    'Time spent processing jobs',
    ['job_type'],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf'))
)

job_queue_wait_histogram = Histogram(
    'job_queue_wait_seconds',
    'Time jobs spend waiting in queue',
    ['job_type']
)

# Gauges - can go up or down
jobs_pending_gauge = Gauge(
    'jobs_pending_count',
    'Current number of pending jobs'
)

jobs_processing_gauge = Gauge(
    'jobs_processing_count',
    'Current number of jobs being processed'
)

worker_up_gauge = Gauge(
    'worker_up',
    'Worker health status (1 = up, 0 = down)'
)
