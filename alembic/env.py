import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context
from dotenv import load_dotenv

# Load .env so ASYNCAI_DB_URL is available when running via CLI
load_dotenv()

# Alembic Config object -- provides access to values in alembic.ini
config = context.config

# Set the DB URL from environment variable (overrides alembic.ini sqlalchemy.url)
config.set_main_option("sqlalchemy.url", os.getenv("ASYNCAI_DB_URL", ""))

# Set up logging from alembic.ini if a config file is present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the unified Base so Alembic sees all model metadata
from asyncai.db.models import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline mode is not supported with the async engine."""
    raise NotImplementedError("Offline mode not supported with async engine")


def do_run_migrations(connection) -> None:
    """Synchronous callback passed to connection.run_sync() -- Alembic requires this."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine, obtain a connection, and run migrations synchronously."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations -- calls the async runner via asyncio.run()."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
