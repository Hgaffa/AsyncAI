import pytest
import pytest_asyncio
import asyncio


def test_registry_empty():
    from asyncai.registry import TaskRegistry
    r = TaskRegistry.instance()
    r._tasks.clear()
    assert r.list_tasks() == []


def test_registry_register_get():
    from asyncai.registry import TaskRegistry
    r = TaskRegistry.instance()
    r._tasks.clear()
    async def my_task(x: int): return x
    r.register("my_task", my_task)
    assert r.get("my_task") is my_task


def test_registry_unknown():
    from asyncai.registry import TaskRegistry
    from asyncai.exceptions import UnknownTaskError
    r = TaskRegistry.instance()
    r._tasks.clear()
    with pytest.raises(UnknownTaskError):
        r.get("nonexistent")


def test_registry_singleton():
    from asyncai.registry import TaskRegistry
    assert TaskRegistry.instance() is TaskRegistry.instance()


def test_task_registers():
    from asyncai.registry import TaskRegistry
    from asyncai.task import task
    r = TaskRegistry.instance()
    r._tasks.clear()
    @task
    async def add(a: int, b: int): return a + b
    assert r.get("add") is not None


def test_task_no_parens():
    from asyncai.registry import TaskRegistry
    from asyncai.task import task
    r = TaskRegistry.instance()
    r._tasks.clear()
    @task
    async def fn_no_parens(x: int): return x
    @task()
    async def fn_with_parens(x: int): return x
    assert r.get("fn_no_parens") is not None
    assert r.get("fn_with_parens") is not None


def test_task_decorator_params():
    from asyncai.registry import TaskRegistry
    from asyncai.task import task
    r = TaskRegistry.instance()
    r._tasks.clear()
    @task(name="custom_name", retries=5, timeout=30, priority=8)
    async def some_func(x: int): return x
    fn = r.get("custom_name")
    assert fn is not None
    assert fn._task_retries == 5
    assert fn._task_timeout == 30
    assert fn._task_priority == 8


@pytest.mark.asyncio
async def test_task_validates_args():
    from pydantic import ValidationError
    from asyncai.task import task
    @task
    async def typed_task(count: int, label: str): pass
    with pytest.raises(ValidationError):
        await typed_task.submit(count="not-an-int", label=42)


def test_task_preserves_signature():
    from asyncai.task import task
    @task
    async def documented(x: int):
        """Multiplies x."""
        return x
    assert documented.__name__ == "documented"
    assert "Multiplies" in (documented.__doc__ or "")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_task_submits_job(async_db_session):
    from asyncai.task import task
    from asyncai.db.models import Job, JobStatus
    from sqlalchemy import select
    @task
    async def enqueue_me(value: int): pass
    job_id = await enqueue_me.submit(value=42)
    assert isinstance(job_id, int)
    result = await async_db_session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one()
    assert job.type == "enqueue_me"
    assert job.status == JobStatus.PENDING
    assert job.payload == {"value": 42}
