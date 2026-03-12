from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from pydantic import create_model

from asyncai._context import _active_step_name, _active_workflow_id
from asyncai.db.models import Job, JobStatus
from asyncai.db.session import AsyncSessionFactory
from asyncai.registry import TaskRegistry


def _build_validator(fn: Callable) -> type:
    """Build a Pydantic model from a function's signature for argument validation."""
    sig = inspect.signature(fn)
    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        annotation = (
            param.annotation
            if param.annotation is not inspect.Parameter.empty
            else Any
        )
        if param.default is inspect.Parameter.empty:
            fields[param_name] = (annotation, ...)
        else:
            fields[param_name] = (annotation, param.default)
    return create_model(fn.__name__ + "_Args", **fields)


def task(
    _fn: Callable | None = None,
    *,
    name: str | None = None,
    retries: int = 3,
    timeout: int | None = None,
    priority: int = 5,
) -> Any:
    """
    Decorator that registers an async function as a named task.

    Supports three usage forms:
        @task
        @task()
        @task(name="custom", retries=5, timeout=30, priority=8)

    The decorated function gains a .submit(**kwargs) coroutine that validates
    arguments via Pydantic, inserts a Job row, and returns the new job id.
    """

    def decorator(fn: Callable) -> Callable:
        task_name = name or fn.__name__
        validator = _build_validator(fn)

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        async def submit(**kwargs: Any) -> int:
            validated = validator(**kwargs)
            payload = validated.model_dump()
            ctx_workflow_id = _active_workflow_id.get()
            ctx_step_name = _active_step_name.get()
            async with AsyncSessionFactory() as session:
                async with session.begin():
                    job = Job(
                        type=task_name,
                        status=JobStatus.PENDING,
                        payload=payload,
                        max_attempts=retries,
                        priority=priority,
                        workflow_id=ctx_workflow_id,
                        step_name=ctx_step_name,
                    )
                    session.add(job)
                    await session.flush()  # populates job.id
                    return job.id  # type: ignore[return-value]

        wrapper.submit = submit  # type: ignore[attr-defined]
        wrapper._task_name = task_name  # type: ignore[attr-defined]
        wrapper._task_retries = retries  # type: ignore[attr-defined]
        wrapper._task_timeout = timeout  # type: ignore[attr-defined]
        wrapper._task_priority = priority  # type: ignore[attr-defined]

        # Register the wrapper so introspection attributes are accessible
        # via TaskRegistry.instance().get(name)
        TaskRegistry.instance().register(task_name, wrapper)
        return wrapper

    if _fn is not None:
        # Called as @task (no parentheses)
        return decorator(_fn)

    # Called as @task() or @task(name=..., retries=..., ...)
    return decorator


__all__ = ["task"]
