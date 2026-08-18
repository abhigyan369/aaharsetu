"""
migrations/env.py — Alembic Migration Environment (Async Edition)
=================================================================

WHY THIS FILE EXISTS:
  Alembic runs this file every time you create or apply a migration.
  It's responsible for:
    1. Connecting to the database
    2. Telling Alembic which tables to track (via target_metadata)
    3. Running migrations in either "offline" or "online" mode

  We've configured it to work with SQLAlchemy's async engine (asyncio mode).
  This is necessary because our app uses async SQLAlchemy — using the default
  sync env.py would cause import errors.

INTERVIEW TALKING POINT:
  "Alembic autogenerate compares our SQLAlchemy models against the live
  database schema and generates SQL migration scripts automatically.
  We commit those scripts to git, so every developer and the production
  server runs exactly the same schema changes in order."

HOW TO USE:
  # Create a new migration after changing a model:
  alembic revision --autogenerate -m "describe your change"

  # Apply all pending migrations to the database:
  alembic upgrade head

  # Roll back the last migration:
  alembic downgrade -1
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Import your settings so we can read DATABASE_URL from .env ────────────────
from app.core.config import settings

# ── Import Base + all models so Alembic can see the full schema ───────────────
# This is the crucial step — if you add a new model and forget to import it
# here (or in app/db/base.py), autogenerate won't see it!
from app.db.base import Base  # noqa: F401

# Import app.models package — its __init__.py registers all four models
# (User, FoodListing, Claim, Notification) with Base.metadata in one shot.
# If you add a new model, add it to app/models/__init__.py.
import app.models  # noqa: F401

# ─────────────────────────────────────────────────────────────────────────────
config = context.config

# Load logging configuration from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url in alembic.ini with our pydantic-settings value.
# This way we have ONE source of truth (.env) instead of duplicating the URL.
#
# NOTE: configparser uses % for interpolation (e.g. %(here)s), so any literal
# % in the value — such as %40 (URL-encoded @) in a password — must be escaped
# as %%. We do that here so URLs like postgresql+asyncpg://user:p%40ss@host/db
# are stored correctly and don't raise ValueError at parse time.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# target_metadata tells autogenerate what schema to compare against.
# Point it at Base.metadata so Alembic sees all your models.
target_metadata = Base.metadata


# ── Offline Mode ──────────────────────────────────────────────────────────────
# "Offline" = generate SQL scripts without connecting to the DB.
# Useful for generating migration SQL to review before applying.
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online Mode (Async) ───────────────────────────────────────────────────────
# "Online" = connect to the real DB and apply changes.
# We use the async engine here to stay consistent with our app's DB layer.
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations within it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No pooling in migration scripts — run and exit
    )
    async with connectable.connect() as connection:
        # run_sync wraps the sync Alembic API so it works inside an async context
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ── Entry Point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
