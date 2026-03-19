asyncai.workflow
================

The ``@workflow`` decorator registers an async function as a named, durable
workflow. Like ``@task``, it adds a ``.submit(**kwargs)`` coroutine, but that
coroutine creates both a ``Workflow`` row and a linked ``Job`` row atomically,
and returns a :class:`~asyncai.workflow.WorkflowHandle` instead of a plain id.

Workflow functions may call :func:`~asyncai.gather.gather` to fan out to child
tasks. The gather step is idempotent — if the worker crashes and the workflow is
retried, already-completed child jobs are reused rather than re-submitted.

Usage::

   from asyncai import workflow, gather, task

   @task
   async def process_item(item: str) -> dict:
       return {"processed": item}

   @workflow
   async def process_all(items: list[str]) -> dict:
       results = await gather(
           [process_item.submit(item=i) for i in items],
           step_name="process_step",
       )
       return {"results": results}

   # In an async context:
   handle = await process_all.submit(items=["a", "b", "c"])
   result = await handle.result()   # blocks until COMPLETED or FAILED

.. automodule:: asyncai.workflow
   :members:
   :undoc-members:
   :show-inheritance:
