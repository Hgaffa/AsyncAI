asyncai
=======

**Zero-infrastructure persistent AI workflows** — PostgreSQL + decorators only.

asyncai lets you write crash-resistant, parallel AI workflows using nothing but a
PostgreSQL instance and three decorator lines. No Celery, no Redis, no separate
orchestration service. Fan out tasks in parallel with :func:`~asyncai.gather.gather`,
survive process crashes mid-run, and inspect every job from the CLI.

**Key features**

- ``@task`` and ``@workflow`` decorators — turn any async function into a durable job
- ``gather()`` — parallel fan-out with ordered results and idempotent restart
- Crash recovery — jobs left in ``PROCESSING`` are automatically re-queued on startup
- Priority scheduling — higher-priority jobs are dequeued first
- Built-in CLI — migrate the database, start workers, and inspect jobs without extra tools


Installation
------------

.. code-block:: bash

   pip install asyncai

Or from source:

.. code-block:: bash

   git clone https://github.com/your-org/asyncai
   cd asyncai
   pip install -e ".[dev]"


Configuration
-------------

Set ``ASYNCAI_DB_URL`` to a PostgreSQL connection string, then run migrations:

.. code-block:: bash

   export ASYNCAI_DB_URL=postgresql+asyncpg://user:pass@localhost/mydb
   asyncai db migrate

Both the worker process and any script that submits workflows need
``ASYNCAI_DB_URL`` set. A ``.env`` file in the working directory is loaded
automatically.


Quickstart
----------

Define tasks and a workflow in ``my_workflow.py``:

.. code-block:: python

   from asyncai import task, workflow, gather

   @task
   async def double_one(x: int) -> dict:
       return {"result": x * 2}

   @workflow
   async def double_all(numbers: list[int]) -> dict:
       results = await gather(
           [double_one.submit(x=n) for n in numbers],
           step_name="double_step",
       )
       return {"results": results}

Start a worker in one terminal:

.. code-block:: bash

   asyncai worker start --app my_workflow --concurrency 4

Submit the workflow and wait for the result:

.. code-block:: python

   import asyncio
   from my_workflow import double_all

   async def main():
       handle = await double_all.submit(numbers=[1, 2, 3, 4, 5])
       result = await handle.result()
       print(result)
       # {"results": [{"result": 2}, {"result": 4}, {"result": 6}, ...]}

   asyncio.run(main())

:func:`~asyncai.workflow.WorkflowHandle.result` polls the database until the
workflow reaches ``COMPLETED`` or ``FAILED``, then returns the stored output
(or raises :exc:`~asyncai.exceptions.WorkflowError` on failure).


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api/index
