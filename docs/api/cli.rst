asyncai.cli
===========

The ``asyncai`` CLI is the primary operator interface. It is installed as a
console script entry point by ``pyproject.toml`` and loads ``ASYNCAI_DB_URL``
from a ``.env`` file in the working directory automatically.

**Available commands**

.. code-block:: text

   asyncai db migrate                         Apply Alembic migrations to head
   asyncai worker start --app MODULE          Import MODULE and start the worker
                        --concurrency N       Maximum concurrent jobs (default: 10)
   asyncai workflows [--limit N]              List recent workflows
   asyncai workflow  <UUID>                   Inspect a single workflow and its steps
   asyncai jobs      [--limit N]              List recent standalone task jobs
   asyncai job       <ID>                     Inspect a single standalone job

.. automodule:: asyncai.cli
   :members:
   :undoc-members:
   :show-inheritance:
