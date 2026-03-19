"""
Async SQLAlchemy engine and session factory for asyncai.

Exports:
    engine: AsyncEngine (None if ASYNCAI_DB_URL is not set)
    AsyncSessionFactory: async_sessionmaker[AsyncSession]
"""
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)

load_dotenv()

DATABASE_URL: str | None = os.getenv("ASYNCAI_DB_URL")

if DATABASE_URL is not None:
    engine: AsyncEngine | None = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
else:
    engine = None

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

__all__ = ["engine", "AsyncSessionFactory"]
