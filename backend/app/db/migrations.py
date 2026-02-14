from __future__ import annotations

import asyncio
import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def _backend_root() -> Path:
    # backend/app/db/migrations.py -> backend/
    return Path(__file__).resolve().parents[2]


def _run_upgrade_head_sync(*, database_url: str) -> None:
    backend_root = _backend_root()
    ini_path = backend_root / "alembic.ini"
    if not ini_path.exists():
        raise FileNotFoundError(f"Missing alembic.ini at {ini_path}")

    # Ensure env.py sees the configured DB URL.
    os.environ["AGENTPRESS_DATABASE_URL"] = database_url

    cfg = Config(str(ini_path))
    # Make script_location independent of CWD.
    cfg.set_main_option("script_location", str(backend_root / "alembic"))

    command.upgrade(cfg, "head")


async def upgrade_to_head(*, database_url: str) -> None:
    # Alembic runs sync; offload to a worker thread.
    await asyncio.to_thread(_run_upgrade_head_sync, database_url=database_url)
