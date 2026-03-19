asyncai.gather
==============

:func:`~asyncai.gather.gather` submits a list of task coroutines in parallel and
waits for all of them to reach a terminal state (``COMPLETED`` or ``FAILED``).
Results are returned in submission order.

**Idempotent restart** — if ``gather()`` is called a second time for the same
``step_name`` within the same workflow (e.g. after a crash-recovery), it detects
the existing child jobs in the database and reuses their results without
re-submitting.

``gather()`` must be called from inside a ``@workflow`` function. Calling it
outside a workflow raises :exc:`~asyncai.exceptions.WorkflowError`.

An inline :class:`~asyncai.worker.AsyncWorker` is spawned automatically so that
gather works in single-process environments (tests, scripts) without a separate
worker process. Any external worker will also race to claim the submitted jobs;
``SELECT FOR UPDATE SKIP LOCKED`` ensures each job is executed exactly once.

.. automodule:: asyncai.gather
   :members:
   :undoc-members:
   :show-inheritance:
