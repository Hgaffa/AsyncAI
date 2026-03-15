"""Exception hierarchy for the asyncai package."""

class AsyncAIError(Exception):
    """Base class for all asyncai exceptions."""


class UnknownTaskError(AsyncAIError):
    """Raised when a task name is not found in the TaskRegistry."""


class WorkflowError(AsyncAIError):
    """Raised for errors encountered during workflow execution."""
