import pytest
from importlib.metadata import metadata


def test_import_asyncai():
    import asyncai
    assert asyncai is not None


def test_top_level_exports():
    import asyncai
    assert hasattr(asyncai, "task")
    assert hasattr(asyncai, "workflow")
    assert hasattr(asyncai, "gather")


def test_exception_classes():
    from asyncai.exceptions import AsyncAIError, UnknownTaskError, WorkflowError
    assert issubclass(UnknownTaskError, AsyncAIError)
    assert issubclass(WorkflowError, AsyncAIError)


def test_pyproject_metadata():
    meta = metadata("asyncai")
    assert meta["Name"] == "asyncai"
    assert meta["Version"] is not None


def test_db_package_exists():
    import asyncai.db
    assert asyncai.db is not None
