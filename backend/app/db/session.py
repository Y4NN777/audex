from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel

from app.core.config import settings
from app.db.engine import get_async_engine

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = get_async_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        await session.close()


async def init_db() -> None:
    async with get_engine().begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
