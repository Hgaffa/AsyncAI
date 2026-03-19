asyncai.worker
==============

:class:`~asyncai.worker.AsyncWorker` is a bounded-concurrency job runner that
polls PostgreSQL for ``PENDING`` jobs using ``SELECT FOR UPDATE SKIP LOCKED``.
Multiple worker processes may run concurrently — the ``SKIP LOCKED`` clause
ensures each job is claimed by exactly one worker.

:func:`~asyncai.worker.recover_crashed_jobs` resets any jobs left in
``PROCESSING`` back to ``PENDING``. It should be called once at worker startup
before the polling loop begins (the CLI does this automatically via
``asyncai worker start``).

:func:`~asyncai.worker.poll_and_run_one` claims and executes a single job using
a two-transaction pattern within one session:

1. **Tx1** — atomically claim the highest-priority ``PENDING`` job.
2. **Tx2** — dispatch to the registered task function, then persist the outcome
   (``COMPLETED`` + ``TaskResult`` on success; ``FAILED`` or back to ``PENDING``
   for retry on error).

.. automodule:: asyncai.worker
   :members:
   :undoc-members:
   :show-inheritance:
