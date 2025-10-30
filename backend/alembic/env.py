from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

from app.core.config import settings
from app.db.engine import get_async_engine
from app import models  # noqa: F401 - ensure models are imported for metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = get_async_engine()

    async def run() -> None:
        async with connectable.begin() as connection:
            await connection.run_sync(run_migrations)

    def run_migrations(connection) -> None:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()

    asyncio.run(run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
