"""
Test configuration and fixtures
Based on official FastAPI testing documentation
"""
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import pytest

# SQLite test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

from app.db import Base, get_db
from app.main import app
from fastapi.testclient import TestClient

_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

_TESTINGSESSIONLOCAL = sessionmaker(
    autocommit=False, autoflush=False, bind=_engine)


def override_get_db() -> Generator[Session, None, None]:
    """Dependency override for database session"""
    try:
        db = _TESTINGSESSIONLOCAL()
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create tables before each test and drop after"""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def client() -> Generator["TestClient", None, None]:
    """Create a test client with database override"""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create a database session for direct database access in tests"""
    connection = _engine.connect()
    transaction = connection.begin()
    session = _TESTINGSESSIONLOCAL(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# TaskRegistry isolation — prevent test_task.py's r._tasks.clear() calls from
# destroying module-level workflow/task registrations needed by later tests.
# ---------------------------------------------------------------------------
try:
    from asyncai.registry import TaskRegistry as _TaskRegistry

    @pytest.fixture(autouse=True)
    def _preserve_task_registry():
        """Save and restore TaskRegistry state around every test."""
        registry = _TaskRegistry.instance()
        saved = dict(registry._tasks)
        yield
        registry._tasks = saved

except ImportError:
    pass  # asyncai not yet available


# Cleanup test database file
def pytest_sessionfinish():
    """Cleanup after all tests are done"""
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Async fixtures for Phase 2 (asyncai worker/task integration tests)
# ---------------------------------------------------------------------------
try:
    import pytest_asyncio
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession
    from asyncai.db.session import engine as async_engine, AsyncSessionFactory
    from asyncai.db.models import Base as AsyncBase, Job, TaskResult, Workflow, WorkflowStep

    @pytest_asyncio.fixture
    async def async_db_session():
        if async_engine is None:
            pytest.skip("ASYNCAI_DB_URL not set")
        async with async_engine.begin() as conn:
            await conn.run_sync(AsyncBase.metadata.create_all)
        # Clean up leftover rows from previous tests so each test starts fresh.
        # Order matters: delete dependents before parents to satisfy FK constraints.
        async with AsyncSessionFactory() as session:
            async with session.begin():
                await session.execute(delete(TaskResult))   # FK → job
                await session.execute(delete(WorkflowStep)) # FK → workflows
                await session.execute(delete(Job))          # FK → workflows (SET NULL, but delete first)
                await session.execute(delete(Workflow))
        async with AsyncSessionFactory() as session:
            yield session
        # Drain the connection pool before the function-scoped event loop closes.
        # Without this, asyncpg schedules callbacks on the loop AFTER it's closed,
        # which corrupts the next test's setup with "Event loop is closed" errors.
        await async_engine.dispose()

except ImportError:
    pass  # asyncai async modules not yet available
