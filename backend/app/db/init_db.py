from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.settings import settings
from app.db.models import Base
from app.db.session import engine


async def init_db() -> None:
    if not settings.auto_create_tables:
        return

    url = make_url(settings.database_url)
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        db_path = Path(url.database)
        if not db_path.is_absolute():
            db_path = (Path.cwd() / db_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
