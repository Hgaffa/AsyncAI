from __future__ import annotations

from typing import Any, Callable

from asyncai.exceptions import UnknownTaskError


class TaskRegistry:
    """Singleton registry mapping task names to callable functions."""

    _instance: TaskRegistry | None = None

    def __init__(self) -> None:
        self._tasks: dict[str, Callable[..., Any]] = {}

    @classmethod
    def instance(cls) -> TaskRegistry:
        """Return the singleton instance, creating it if necessary."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a callable under the given name."""
        self._tasks[name] = fn

    def get(self, name: str) -> Callable[..., Any]:
        """Return the callable registered under name, or raise UnknownTaskError."""
        if name not in self._tasks:
            raise UnknownTaskError(f"No task registered: {name}")
        return self._tasks[name]

    def list_tasks(self) -> list[str]:
        """Return a list of all registered task names."""
        return list(self._tasks.keys())


__all__ = ["TaskRegistry"]
