"""
Synchronous SQLAlchemy database setup for the FastAPI application.

Exports ``engine``, ``Base``, and ``get_db`` for use with FastAPI's
dependency injection system.  Uses ``DATABASE_URL`` from the environment;
importing this module without ``DATABASE_URL`` set will raise ``ArgumentError``
at engine creation time, so callers must guard against that.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {},
)
SESSIONLOCAL = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all app ORM models."""


def get_db():
    """FastAPI dependency that yields a database session and ensures it is
    closed after the request, whether or not an exception occurred."""
    db = SESSIONLOCAL()
    try:
        yield db
    finally:
        db.close()
