"""
tests/test_auth.py — Authentication & Authorization Tests
===========================================================

TESTS IN THIS MODULE:
  1. Signup Flow:
     - test_signup_donor_success: Successful registration as donor
     - test_signup_receiver_success: Successful registration as receiver
     - test_signup_duplicate_email: Rejection of already-used email (400 Bad Request)
     - test_signup_admin_blocked: Self-registration as admin is forbidden (400 Bad Request)
     - test_signup_validation_error: Missing required fields (422 Unprocessable Entity)

  2. Login Flow:
     - test_login_success: Valid credentials return access and refresh JWT tokens
     - test_login_wrong_password: Bad password returns 401 Unauthorized
     - test_login_nonexistent_user: Unknown email returns 401 Unauthorized

  3. Protected Routes & Identity:
     - test_get_me_unauthenticated: GET /auth/me without token returns 401
     - test_get_me_invalid_token: GET /auth/me with garbage token returns 401
     - test_get_me_success: GET /auth/me with valid Bearer token returns profile without password
"""

import pytest
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


# ── 1. Signup Tests ───────────────────────────────────────────────────────────
async def test_signup_donor_success(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify that a user can register as a donor and password is never returned."""
    payload = {
        "name": "Sarah Baker",
        "email": "sarah.baker@example.com",
        "password": "StrongPassword123!",
        "role": "donor",
        "phone": "+1234567890",
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()

    # Verify returned schema
    assert data["name"] == "Sarah Baker"
    assert data["email"] == "sarah.baker@example.com"
    assert data["role"] == "donor"
    assert "id" in data
    # Password and hash must NEVER be returned in any response
    assert "password" not in data
    assert "hashed_password" not in data

    # Verify DB persistence
    result = await db_session.execute(select(User).where(User.email == "sarah.baker@example.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.name == "Sarah Baker"
    assert user.role == UserRole.DONOR


async def test_signup_receiver_success(client: httpx.AsyncClient):
    """Verify that a user can register as a receiver."""
    payload = {
        "name": "Community Shelter",
        "email": "shelter@example.com",
        "password": "SecurePassword456!",
        "role": "receiver",
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "receiver"
    assert data["email"] == "shelter@example.com"


async def test_signup_duplicate_email(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that registering with an existing email returns 400 Bad Request."""
    user, _, _ = donor_user
    payload = {
        "name": "Imposter",
        "email": user.email,  # same email as existing fixture
        "password": "AnotherPassword789!",
        "role": "donor",
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


async def test_signup_admin_blocked(client: httpx.AsyncClient):
    """Verify that self-signup as admin is explicitly rejected (must be seeded)."""
    payload = {
        "name": "Malicious Admin",
        "email": "hacker@example.com",
        "password": "AdminPassword123!",
        "role": "admin",
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 400
    assert "admin" in response.json()["detail"].lower()


async def test_signup_validation_error(client: httpx.AsyncClient):
    """Verify Pydantic validation: invalid email or missing password triggers 422."""
    payload = {
        "name": "Invalid User",
        "email": "not-an-email",
        "role": "donor",
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


# ── 2. Login Tests ────────────────────────────────────────────────────────────
async def test_login_success(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify valid login returns access_token, refresh_token, and token_type."""
    user, _, _ = donor_user
    # OAuth2 spec requires form-data POST with username & password fields
    response = await client.post(
        "/auth/login",
        data={
            "username": user.email,
            "password": "SecretPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"].lower() == "bearer"
    assert len(data["access_token"]) > 20


async def test_login_wrong_password(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify login with incorrect password returns 401 Unauthorized."""
    user, _, _ = donor_user
    response = await client.post(
        "/auth/login",
        data={
            "username": user.email,
            "password": "WrongPassword!",
        },
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()
    assert response.headers.get("www-authenticate") == "Bearer"


async def test_login_nonexistent_user(client: httpx.AsyncClient):
    """Verify login with non-existent email returns 401 Unauthorized."""
    response = await client.post(
        "/auth/login",
        data={
            "username": "ghost@nonexistent.com",
            "password": "SomePassword123!",
        },
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


# ── 3. Protected Route & Identity Tests ───────────────────────────────────────
async def test_get_me_unauthenticated(client: httpx.AsyncClient):
    """Verify accessing protected GET /auth/me without Authorization header returns 401."""
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


async def test_get_me_invalid_token(client: httpx.AsyncClient):
    """Verify accessing GET /auth/me with an invalid token returns 401."""
    headers = {"Authorization": "Bearer invalid.token.payload"}
    response = await client.get("/auth/me", headers=headers)
    assert response.status_code == 401


async def test_get_me_success(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify accessing GET /auth/me with valid Bearer token returns user profile."""
    user, _, headers = donor_user
    response = await client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["email"] == user.email
    assert data["name"] == user.name
    assert data["role"] == "donor"
    assert "hashed_password" not in data
