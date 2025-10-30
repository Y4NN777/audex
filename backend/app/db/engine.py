from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from app.core.config import settings

_engine: AsyncEngine | None = None


def get_async_engine() -> AsyncEngine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = _create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
    return _engine


engine = get_async_engine()
