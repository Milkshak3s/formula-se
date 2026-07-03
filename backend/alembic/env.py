from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.config import settings
from app.core.database import Base
import app.models  # noqa: F401 — ensure all models are imported for autogenerate

# A constant session-level advisory lock key so that if several pods run
# `alembic upgrade head` concurrently (e.g. multiple replicas' init containers),
# only one migrates at a time and the rest no-op once it's at head.
_MIGRATION_LOCK_KEY = 728_411_053

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Serialize concurrent migrators with a session-level advisory lock.
        # Commit immediately after acquiring so this statement's transaction
        # doesn't stay open and swallow Alembic's own migration transaction
        # (which would roll the migrations back on connection close). A
        # session-level lock survives the commit and is released explicitly
        # below (and by the session ending, so it can't leak on crash).
        connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _MIGRATION_LOCK_KEY})
        connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": _MIGRATION_LOCK_KEY}
            )
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
