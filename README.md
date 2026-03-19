# asyncai

**Zero-infrastructure persistent AI workflows** — PostgreSQL + decorators only.

asyncai lets you write crash-resistant, parallel AI workflows using nothing but a PostgreSQL
instance and three decorator lines. No Celery, no Redis, no separate orchestration service.
Fan out tasks in parallel with `gather()`, survive process crashes mid-run, and inspect every
job from the CLI.

---

## Prerequisites

- Python 3.10+
- A running PostgreSQL instance
- `ASYNCAI_DB_URL` environment variable pointing at it

---

## Installation

```bash
pip install asyncai
```

Or from source:

```bash
git clone https://github.com/your-org/asyncai
cd asyncai
pip install -e ".[dev]"
```

---

## Configuration

```bash
export ASYNCAI_DB_URL=postgresql+asyncpg://user:pass@localhost/mydb
asyncai db migrate
```

Both the worker process and any script that submits workflows need `ASYNCAI_DB_URL` set.

---

## Quickstart: double_all example

This example fans out across a list of numbers — each number is doubled in a separate task
running in parallel, and `gather()` collects all results before the workflow returns.

**Create `my_workflow.py`:**

```python
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
```

**Terminal 1 — start the worker:**

```bash
export ASYNCAI_DB_URL=postgresql+asyncpg://user:pass@localhost/mydb
asyncai worker start --app my_workflow --concurrency 4
```

The worker imports `my_workflow`, discovers all `@task` and `@workflow` decorators, then
polls for jobs using `SELECT ... FOR UPDATE SKIP LOCKED` so multiple workers never double-
process the same job.

**Terminal 2 (or a script) — submit the workflow and await the result:**

```python
import asyncio
from my_workflow import double_all

async def main():
    handle = await double_all.submit(numbers=[1, 2, 3, 4, 5])
    result = await handle.result()
    print(result)  # {"results": [{"result": 2}, {"result": 4}, {"result": 6}, {"result": 8}, {"result": 10}]}

asyncio.run(main())
```

`handle.result()` polls the database until the workflow job reaches `COMPLETED` or `FAILED`,
then returns the stored output (or raises on failure).

---

## CLI reference

| Command | Description |
|---|---|
| `asyncai db migrate` | Run Alembic migrations to create the jobs/workflows tables |
| `asyncai worker start --app MODULE --concurrency N` | Start a worker process loading tasks from MODULE |
| `asyncai workflows` | List recent workflows with status and step timeline |
| `asyncai workflow JOB_ID` | Show detail for a single workflow job |
| `asyncai jobs` | List recent standalone task jobs (not part of a workflow) |
| `asyncai job JOB_ID` | Show detail for a single job |

---

## Key concepts

- **`@task`** — Decorates an async function. Adds a `.submit(**kwargs)` coroutine that
  validates arguments via Pydantic, persists the call to the database, and returns the
  new job's `int` id.
- **`@workflow`** — Like `@task` but for orchestrator functions. The decorated function may
  call `gather()` to fan out to child tasks.
- **`gather(submissions, step_name)`** — Submits a list of task coroutines in parallel,
  waits for all to complete, and returns their results in order. Idempotent: re-running
  after a crash will not re-submit already-completed child jobs.
- **`WorkflowHandle`** — Returned by `workflow.submit()`. Call `.result()` to poll for and
  return the workflow's output, or `.status()` to check the current state.
- **Crash recovery** — If the worker dies mid-run, jobs left in `PROCESSING` state are
  reset to `PENDING` on next startup so they are retried automatically.

---

## Running the test suite

```bash
# Unit tests (no database required):
pytest

# Integration tests (requires ASYNCAI_DB_URL):
pytest -m integration
```

---

## API documentation

Full API reference (auto-generated from docstrings):

```bash
pip install sphinx furo
sphinx-build -b html docs/ docs/_build/html
open docs/_build/html/index.html
```

---

## License

MIT
