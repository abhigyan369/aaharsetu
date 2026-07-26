"""
app/db/database.py — Async Database Engine & Session Factory
=============================================================

WHY THIS FILE EXISTS:
  SQLAlchemy needs two things to talk to a database:
    1. An **Engine** — the connection pool (reuses DB connections efficiently)
    2. A **Session** — a "unit of work" that tracks changes and flushes them
       to the DB in one transaction

  We use async versions of both because FastAPI is async-native.
  Mixing sync database calls in an async app would block the event loop,
  killing concurrency — imagine one slow DB query pausing all other requests.

INTERVIEW TALKING POINT:
  "SQLAlchemy's async engine uses asyncpg under the hood. Each request gets
  its own session (dependency-injected), so there are no shared-state bugs
  between concurrent requests."
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
# `create_async_engine` sets up a connection pool to the database.
# `echo=settings.DEBUG` logs every SQL statement when DEBUG=true — very useful
# during development, but too noisy (and a security risk) in production.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # pool_pre_ping=True: test connections before handing them out — prevents
    # "connection closed" errors after the DB restarts or idles too long.
    pool_pre_ping=True,
)

# ── Session Factory ───────────────────────────────────────────────────────────
# `async_sessionmaker` is a factory that produces new AsyncSession objects.
# - expire_on_commit=False: after commit(), don't expire ORM objects so we
#   can still read their attributes without issuing another SELECT.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.

    HOW DEPENDENCY INJECTION WORKS HERE:
      When a route declares `db: AsyncSession = Depends(get_db)`, FastAPI:
        1. Calls get_db() and runs it up to the `yield`
        2. Injects the session into the route function
        3. After the route finishes (success OR exception), resumes after
           `yield` and closes the session

    WHY `yield` instead of `return`?
      Using `yield` makes this a context manager — the `finally` block always
      runs, so the session is always closed even if the route throws an error.
      This prevents connection leaks.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
