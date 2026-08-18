"""
tests/conftest.py — Pytest Configuration & Fixtures
====================================================

WHY THIS FILE EXISTS:
  This file configures the test environment for the Food Waste Redistribution Platform.
  It sets up an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) that
  creates fresh tables before each test and cleans them up afterward.

TEST ISOLATION PATTERN:
  1. We create an async SQLite engine with StaticPool so in-memory connections share state.
  2. We override FastAPI's `get_db` dependency to yield sessions bound to the test engine.
  3. We mock external services (Cloudinary upload, SMTP email delivery, APScheduler)
     so tests run completely offline and lightning-fast.
"""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.database import get_db
import app.db.database as db_module
import app.routers.listings as listings_module
import app.core.scheduler as scheduler_module
from app.main import app
from app.models.user import User, UserRole

# ── Test Database Engine ──────────────────────────────────────────────────────
# `sqlite+aiosqlite:///:memory:` creates a pure in-memory SQLite database.
# `StaticPool` ensures all async connections within a test share the exact same
# in-memory database instance.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Database Lifecycle Fixture ────────────────────────────────────────────────
@pytest_asyncio.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """
    Autouse fixture that creates all tables before each test and drops them after.
    Patches module-level session factories so background tasks use the test DB.
    """
    # Patch module-level engine and sessionmaker references
    orig_db_engine = db_module.engine
    orig_db_session_local = db_module.AsyncSessionLocal
    orig_listings_session_local = listings_module.AsyncSessionLocal
    orig_scheduler_session_local = scheduler_module.AsyncSessionLocal

    db_module.engine = test_engine
    db_module.AsyncSessionLocal = TestAsyncSessionLocal
    listings_module.AsyncSessionLocal = TestAsyncSessionLocal
    scheduler_module.AsyncSessionLocal = TestAsyncSessionLocal

    # Create tables in the in-memory SQLite database
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Drop all tables after the test finishes for complete isolation
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Restore original references
    db_module.engine = orig_db_engine
    db_module.AsyncSessionLocal = orig_db_session_local
    listings_module.AsyncSessionLocal = orig_listings_session_local
    scheduler_module.AsyncSessionLocal = orig_scheduler_session_local


# ── Database Session Fixture ──────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a dedicated AsyncSession connected to the test database."""
    async with TestAsyncSessionLocal() as session:
        yield session


# ── Mock External Services Fixture ───────────────────────────────────────────
@pytest_asyncio.fixture(autouse=True)
def mock_external_services():
    """
    Mock external side-effects so tests never attempt real network I/O:
    - Cloudinary upload returns a deterministic placeholder CDN URL.
    - send_email is an AsyncMock that records calls without contacting SMTP.
    - APScheduler start/shutdown are no-ops during test lifespan.
    """
    async def mock_upload(file=None):
        return "https://res.cloudinary.com/demo/image/upload/sample.jpg"

    with (
        patch("app.routers.listings.upload_image", side_effect=mock_upload),
        patch("app.core.cloudinary_service.upload_image", side_effect=mock_upload),
        patch("app.core.email_service.send_email", new_callable=AsyncMock),
        patch("app.routers.listings.send_email", new_callable=AsyncMock),
        patch("app.core.scheduler.scheduler.start"),
        patch("app.core.scheduler.scheduler.shutdown"),
    ):
        yield


# ── Async Test Client Fixture ─────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    FastAPI Async Test Client powered by httpx.
    Overrides the `get_db` dependency with `TestAsyncSessionLocal`.
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestAsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── User & Token Helper Fixtures ──────────────────────────────────────────────
async def _create_test_user(
    session: AsyncSession,
    name: str,
    email: str,
    role: UserRole,
    password: str = "SecretPassword123!",
) -> tuple[User, str, dict[str, str]]:
    """Helper to persist a user, generate an access token, and return auth headers."""
    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}
    return user, token, headers


@pytest_asyncio.fixture
async def donor_user(db_session: AsyncSession) -> tuple[User, str, dict[str, str]]:
    """Primary donor user fixture -> returns (User, token_str, auth_headers_dict)."""
    return await _create_test_user(
        session=db_session,
        name="Alice Donor",
        email="alice.donor@example.com",
        role=UserRole.DONOR,
    )


@pytest_asyncio.fixture
async def receiver_user(db_session: AsyncSession) -> tuple[User, str, dict[str, str]]:
    """Primary receiver user fixture -> returns (User, token_str, auth_headers_dict)."""
    return await _create_test_user(
        session=db_session,
        name="Bob Receiver",
        email="bob.receiver@example.com",
        role=UserRole.RECEIVER,
    )


@pytest_asyncio.fixture
async def other_donor_user(db_session: AsyncSession) -> tuple[User, str, dict[str, str]]:
    """Secondary donor user fixture (for ownership/permission check tests)."""
    return await _create_test_user(
        session=db_session,
        name="Charlie Donor",
        email="charlie.donor@example.com",
        role=UserRole.DONOR,
    )


@pytest_asyncio.fixture
async def other_receiver_user(db_session: AsyncSession) -> tuple[User, str, dict[str, str]]:
    """Secondary receiver user fixture (for double-claim race condition tests)."""
    return await _create_test_user(
        session=db_session,
        name="Dave Receiver",
        email="dave.receiver@example.com",
        role=UserRole.RECEIVER,
    )


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> tuple[User, str, dict[str, str]]:
    """Admin user fixture."""
    return await _create_test_user(
        session=db_session,
        name="Admin User",
        email="admin@example.com",
        role=UserRole.ADMIN,
    )
