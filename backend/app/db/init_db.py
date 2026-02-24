from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.settings import settings
from app.db.migrations import upgrade_to_head
from app.db.models import Base
from app.db.session import engine


logger = logging.getLogger(__name__)


async def init_db() -> None:
    url = make_url(settings.database_url)

    # Prefer real migrations for production-grade databases.
    if settings.run_migrations_on_startup:
        await upgrade_to_head(database_url=settings.database_url)
        return

    if not url.drivername.startswith("sqlite") and settings.auto_create_tables:
        logger.warning(
            "Database URL is non-SQLite (%s) with AGENTPRESS_AUTO_CREATE_TABLES=true. "
            "This may cause schema drift. Prefer Alembic migrations by setting "
            "AGENTPRESS_RUN_MIGRATIONS_ON_STARTUP=true and AGENTPRESS_AUTO_CREATE_TABLES=false.",
            url.drivername,
        )

    if not settings.auto_create_tables:
        return

    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        db_path = Path(url.database)
        if not db_path.is_absolute():
            db_path = (Path.cwd() / db_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        # Lightweight SQLite migration for additive columns.
        if url.drivername.startswith("sqlite"):
            try:
                res = await conn.exec_driver_sql("PRAGMA table_info(agents)")
                existing_cols = {row[1] for row in res.fetchall()}
                if "provider" not in existing_cols:
                    await conn.exec_driver_sql("ALTER TABLE agents ADD COLUMN provider VARCHAR(50) NOT NULL DEFAULT 'ollama'")
                if "allowed_plugins" not in existing_cols:
                    await conn.exec_driver_sql("ALTER TABLE agents ADD COLUMN allowed_plugins JSON")
                if "allowed_tools" not in existing_cols:
                    await conn.exec_driver_sql("ALTER TABLE agents ADD COLUMN allowed_tools JSON")
            except Exception:
                # If the table doesn't exist yet or ALTER fails, create_all below will handle new DBs.
                pass

            try:
                res = await conn.exec_driver_sql("PRAGMA table_info(messages)")
                existing_cols = {row[1] for row in res.fetchall()}
                if "token_count" not in existing_cols:
                    await conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN token_count INTEGER")
            except Exception:
                pass

        await conn.run_sync(Base.metadata.create_all)
