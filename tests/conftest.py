"""
Test configuration and fixtures
Based on official FastAPI testing documentation
"""
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app
import pytest

# SQLite test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TESTINGSESSIONLOCAL = sessionmaker(
    autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    """
    Dependency override for database session
    """
    try:
        db = TESTINGSESSIONLOCAL()
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    """
    Create tables before each test and drop after
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Create a test client with database override
    """
    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db

    # Create and yield client
    with TestClient(app) as c:
        yield c

    # Clear overrides
    app.dependency_overrides.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """
    Create a database session for direct database access in tests
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TESTINGSESSIONLOCAL(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# Cleanup test database file
def pytest_sessionfinish():
    """
    Cleanup after all tests are done
    """
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except Exception:
            pass
