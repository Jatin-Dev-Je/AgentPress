from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure `app.*` is importable when Alembic is invoked from a venv script
# (where sys.path[0] is the scripts directory, not the backend root).
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.db.models import Base

# this is the Alembic Config object, which provides access to the values within
# the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def _get_db_url() -> str:
    return (
        os.getenv("AGENTPRESS_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "sqlite+aiosqlite:///./.data/agentpress.db"
    )


def _sync_url(url: str) -> str:
    # Alembic offline mode expects a sync dialect.
    u = make_url(url)
    driver = u.drivername
    if driver.startswith("postgresql+"):
        driver = "postgresql"
    if driver.startswith("sqlite+"):
        driver = "sqlite"
    return str(u.set(drivername=driver))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = _sync_url(_get_db_url())
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # Use an async engine so we can run against async drivers (asyncpg/aiosqlite).
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _get_db_url()

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def _run() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(_run())


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
