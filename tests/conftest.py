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

# Guard: only import app.db/app.main if DATABASE_URL is set.
# Without this guard, app.db.create_engine(None) raises ArgumentError at import time,
# breaking unit tests that do not require a live database.
_DATABASE_URL = os.getenv("DATABASE_URL")
_app_imports_available = _DATABASE_URL is not None

if _app_imports_available:
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
        _engine.metadata.create_all(bind=_engine)
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


# Cleanup test database file
def pytest_sessionfinish():
    """Cleanup after all tests are done"""
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except Exception:
            pass
