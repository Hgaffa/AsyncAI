"""
Ambient context variables for asyncai workflow execution.

asyncio-safe ContextVars that flow through the async call stack without
explicit parameter threading. Set by the workflow runner before calling
the user function; read by gather() to link child jobs to the active workflow.
"""
from __future__ import annotations
import contextvars
import uuid

_active_workflow_id: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "_active_workflow_id", default=None
)
_active_step_name: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_active_step_name", default=None
)

__all__ = ["_active_workflow_id", "_active_step_name"]
