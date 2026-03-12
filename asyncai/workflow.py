"""
Workflow decorator and WorkflowHandle for asyncai.

Provides:
  - @workflow decorator: registers an async function as a named workflow,
    adds a .submit(**kwargs) classmethod that creates Workflow + Job rows
    atomically and returns a WorkflowHandle.
  - WorkflowHandle: dataclass with .status() and .result() polling methods.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from asyncai._context import _active_workflow_id
from asyncai.db.models import Job, JobStatus, Workflow, WorkflowStatus
from asyncai.db.session import AsyncSessionFactory
from asyncai.exceptions import WorkflowError
from asyncai.registry import TaskRegistry
from asyncai.task import _build_validator


@dataclass
class WorkflowHandle:
    """Handle returned by workflow.submit(), used to poll status and retrieve results."""

    id: uuid.UUID

    async def status(self) -> WorkflowStatus:
        """Return the current status of this workflow by querying the DB."""
        async with AsyncSessionFactory() as session:
            wf = await session.get(Workflow, self.id)
            if wf is None:
                raise WorkflowError(f"Workflow {self.id} not found")
            return wf.status

    async def result(
        self,
        poll_interval: float = 0.5,
        timeout: float = 600.0,
    ) -> dict:
        """Poll until the workflow reaches COMPLETED or FAILED.

        Returns:
            The workflow's result dict on COMPLETED.

        Raises:
            WorkflowError: If the workflow reached FAILED status.
            TimeoutError: If the deadline is exceeded before terminal status.
        """
        deadline = time.monotonic() + timeout
        while True:
            async with AsyncSessionFactory() as session:
                wf = await session.get(Workflow, self.id)

            if wf is None:
                raise WorkflowError(f"Workflow {self.id} not found")

            if wf.status == WorkflowStatus.COMPLETED:
                return wf.result or {}

            if wf.status == WorkflowStatus.FAILED:
                raise WorkflowError(wf.error or "Workflow failed with no error message")

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Workflow {self.id} did not complete within {timeout}s"
                )

            await asyncio.sleep(poll_interval)


def workflow(
    _fn: Callable | None = None,
    *,
    name: str | None = None,
) -> Any:
    """
    Decorator that registers an async function as a named workflow.

    Supports three usage forms:
        @workflow
        @workflow()
        @workflow(name="custom")

    The decorated function gains a .submit(**kwargs) coroutine that creates
    a Workflow row and a Job row atomically, returning a WorkflowHandle.
    """

    def decorator(fn: Callable) -> Any:
        workflow_name = name or fn.__name__
        internal_name = f"__workflow__.{workflow_name}"
        validator = _build_validator(fn)

        async def _workflow_runner(**kwargs: Any) -> Any:
            """Internal runner registered in TaskRegistry.

            Receives job.payload (which includes __workflow_id__) from the worker.
            """
            # Pop the injected workflow ID from the payload
            workflow_id_raw = kwargs.pop("__workflow_id__")
            workflow_id = uuid.UUID(str(workflow_id_raw))

            # Set the ambient context so gather() can read the active workflow
            token = _active_workflow_id.set(workflow_id)
            try:
                # Mark workflow as RUNNING
                async with AsyncSessionFactory() as session:
                    async with session.begin():
                        wf = await session.get(Workflow, workflow_id)
                        if wf is not None:
                            wf.status = WorkflowStatus.RUNNING

                # Execute the user's workflow function
                try:
                    return_value = await fn(**kwargs)

                    # Build result dict
                    if isinstance(return_value, dict):
                        result_dict = return_value
                    elif return_value is None:
                        result_dict = {}
                    else:
                        result_dict = {"result": return_value}

                    # Persist success
                    async with AsyncSessionFactory() as session:
                        async with session.begin():
                            wf = await session.get(Workflow, workflow_id)
                            if wf is not None:
                                wf.result = result_dict
                                wf.status = WorkflowStatus.COMPLETED

                    return result_dict

                except Exception as exc:  # noqa: BLE001
                    # CRITICAL: Write error BEFORE re-raising so result() does not
                    # poll forever (Pitfall 3 from research notes).
                    async with AsyncSessionFactory() as session:
                        async with session.begin():
                            wf = await session.get(Workflow, workflow_id)
                            if wf is not None:
                                wf.error = str(exc)
                                wf.status = WorkflowStatus.FAILED
                    raise

            finally:
                _active_workflow_id.reset(token)

        # Register the runner in the TaskRegistry under the internal name
        TaskRegistry.instance().register(internal_name, _workflow_runner)

        class WorkflowWrapper:
            """Callable wrapper that preserves the function and exposes .submit()."""

            def __init__(self) -> None:
                self.__name__ = fn.__name__
                self.__doc__ = fn.__doc__
                self.__module__ = fn.__module__
                self._workflow_name = workflow_name
                self._internal_name = internal_name

            async def __call__(self, *args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            @classmethod
            async def submit(cls, **kwargs: Any) -> WorkflowHandle:
                """Create a Workflow row and a linked Job row atomically.

                Returns a WorkflowHandle with the new workflow's UUID.
                """
                # Validate the kwargs against the user function's signature
                validated = validator(**kwargs)
                validated_kwargs = validated.model_dump()

                async with AsyncSessionFactory() as session:
                    async with session.begin():
                        # Create Workflow row first
                        wf = Workflow(
                            status=WorkflowStatus.PENDING,
                            context=validated_kwargs,
                        )
                        session.add(wf)
                        await session.flush()  # populates wf.id

                        # Build job payload: validated kwargs + injected workflow ID
                        payload = {
                            **validated_kwargs,
                            "__workflow_id__": str(wf.id),
                        }

                        # Create Job row linked to the Workflow
                        job = Job(
                            type=internal_name,
                            status=JobStatus.PENDING,
                            payload=payload,
                            workflow_id=wf.id,
                            max_attempts=1,
                            priority=5,
                        )
                        session.add(job)

                        workflow_id = wf.id

                return WorkflowHandle(id=workflow_id)

        wrapper = WorkflowWrapper()
        return wrapper

    if _fn is not None:
        # Called as @workflow (no parentheses)
        return decorator(_fn)

    # Called as @workflow() or @workflow(name=...)
    return decorator


__all__ = ["workflow", "WorkflowHandle"]
