asyncai.task
============

The ``@task`` decorator registers an async function as a named, durable task.
The decorated function gains a ``.submit(**kwargs)`` coroutine that validates
arguments via Pydantic, inserts a ``Job`` row in PostgreSQL, and returns the
new job's ``int`` id. Jobs are executed by any running
:class:`~asyncai.worker.AsyncWorker` that has imported the same module.

Usage::

   from asyncai import task

   @task
   async def send_email(to: str, subject: str) -> dict:
       ...
       return {"status": "sent"}

   # Submit without waiting for the result:
   job_id = await send_email.submit(to="user@example.com", subject="Hello")

Optional parameters (all keyword-only):

- ``name`` — override the registered task name (default: function name)
- ``retries`` — maximum attempts before marking the job ``FAILED`` (default: 3)
- ``timeout`` — per-attempt time limit in seconds (default: ``None``)
- ``priority`` — scheduling priority; higher value runs first (default: 5)

.. automodule:: asyncai.task
   :members:
   :undoc-members:
   :show-inheritance:
