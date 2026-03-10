import os
import pytest

# Set a dummy URL so engine is created (dialect check works without live DB)
os.environ.setdefault("ASYNCAI_DB_URL", "postgresql+asyncpg://test:test@localhost/test")

pytestmark = pytest.mark.integration


def test_session_factory():
    from asyncai.db.session import AsyncSessionFactory, engine
    from sqlalchemy.ext.asyncio import AsyncEngine
    assert engine is not None, "engine should not be None when ASYNCAI_DB_URL is set"
    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+asyncpg"


def test_models_importable():
    from asyncai.db.models import Base, Job, Workflow, WorkflowStep, TaskResult
    assert Job.__tablename__ == "job"
    assert Workflow.__tablename__ == "workflows"
    assert WorkflowStep.__tablename__ == "workflow_steps"
    assert TaskResult.__tablename__ == "task_results"
    cols = {c.key for c in Job.__table__.columns}
    assert "workflow_id" in cols
    assert "step_name" in cols


@pytest.mark.integration
async def test_alembic_migrations():
    """Verify that alembic upgrade head has created the three new tables."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    url = os.environ["ASYNCAI_DB_URL"]
    engine = create_async_engine(url, echo=False)
    async with engine.connect() as conn:
        for table in ("workflows", "workflow_steps", "task_results"):
            result = await conn.execute(text(
                f"SELECT 1 FROM information_schema.tables WHERE table_name='{table}'"
            ))
            assert result.fetchone() is not None, f"Table {table} not found"
    await engine.dispose()


@pytest.mark.integration
async def test_job_new_columns():
    """Verify that alembic upgrade head added workflow_id and step_name to the job table."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    url = os.environ["ASYNCAI_DB_URL"]
    engine = create_async_engine(url, echo=False)
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='job'"
        ))
        cols = {row[0] for row in result.fetchall()}
        assert "workflow_id" in cols
        assert "step_name" in cols
    await engine.dispose()
