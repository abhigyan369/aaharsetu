"""
app/routers/auth.py — Authentication Endpoints
===============================================

ENDPOINTS IN THIS FILE:
  POST /auth/signup  — Register a new donor or receiver account
  POST /auth/login   — Exchange credentials for JWT tokens
  GET  /auth/me      — Return the current user's profile

WHY ALL AUTH ROUTES IN ONE FILE?
  Auth is a cohesive feature: signup → login → identity. Grouping them in
  one router means a developer can open one file and see the entire auth flow.
  The alternative (one file per endpoint) creates unnecessary fragmentation.

INTERVIEW TALKING POINT — OAuth2 Password Flow:
  "POST /auth/login uses OAuth2's Password Grant flow. The client sends
  username + password in form-encoded body (not JSON — that's the spec).
  The server verifies credentials and returns tokens. Subsequent requests
  carry only the access token — credentials never leave the client again."
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


# ── POST /auth/signup ─────────────────────────────────────────────────────────
@router.post(
    "/signup",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (donor or receiver)",
)
async def signup(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Create a new user account.

    SECURITY DECISIONS:
      - Admin accounts cannot be created here. Admin is a privileged role
        that must be seeded by a trusted operator (see scripts/seed_admin.py).
        Exposing admin creation over HTTP would be a critical security flaw —
        even if we "validate" the role, it creates unnecessary attack surface.

      - We return HTTP 400 (not 409 Conflict) for duplicate emails.
        Why? 409 would tell an attacker "this email is registered", enabling
        user enumeration. 400 is vaguer. (For a production app you might send
        a confirmation email instead — "if this email is registered, you'll
        get a link".)

      - The password is hashed BEFORE the User object is created. The
        plaintext never touches SQLAlchemy or the database layer.

    Returns:
      The created user's profile (UserRead) — never includes the password.
    """
    # ── Block admin self-signup ───────────────────────────────────────────────
    # Belt-and-suspenders: UserCreate schema allows all roles (so that admin
    # can use the same schema elsewhere). We enforce the business rule here
    # at the route level, which is the authoritative security boundary.
    if user_in.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Admin accounts cannot be created via self-signup. "
                "Contact a system administrator."
            ),
        )

    # ── Check email uniqueness ─────────────────────────────────────────────────
    # We do this BEFORE hashing the password (which is intentionally slow)
    # to avoid wasting CPU on a bcrypt hash that we'll immediately discard.
    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    # ── Hash the password ──────────────────────────────────────────────────────
    # hash_password() calls bcrypt, which is deliberately slow (cost factor 12).
    # This means a stolen database is much harder to brute-force offline —
    # each attempt costs ~100ms of CPU on modern hardware.
    hashed = hash_password(user_in.password)

    # ── Create the User ORM object ─────────────────────────────────────────────
    # Note: `user_in.password` (plaintext) is intentionally NOT passed here.
    # We construct the model manually to be explicit about what enters the DB.
    new_user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hashed,   # only the hash goes in
        role=user_in.role,
        phone=user_in.phone,
        is_verified=False,        # email verification happens in a later phase
    )

    db.add(new_user)
    await db.commit()
    # refresh() re-fetches the row from the DB so that server-generated
    # fields like `id` and `created_at` (set by Postgres server_default)
    # are populated on the Python object.
    await db.refresh(new_user)

    return new_user


# ── POST /auth/login ──────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT tokens",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Authenticate a user and return access + refresh tokens.

    WHY OAuth2PasswordRequestForm (not a JSON body)?
      The OAuth2 spec (RFC 6749) defines the Password Grant as a form POST
      with `username` and `password` fields. FastAPI's `OAuth2PasswordRequestForm`
      implements exactly this. Using it means Swagger UI's "Authorize" button
      works out of the box — convenient for testing and demos.

      The `username` field in the form holds the email address. This is a
      naming quirk of the OAuth2 spec — `username` is just the identity
      credential, regardless of whether it's an email or a username string.

    TOKEN STRATEGY:
      - Access token: short-lived (30 min by default from settings).
        Sent in the Authorization header on every protected request.
      - Refresh token: long-lived (7 days). Should be stored more securely
        (httpOnly cookie in a browser app). Used only to get a new access token.

    SECURITY: We use the same error message for "user not found" and "wrong
      password" to prevent user enumeration via timing or message differences.
      verify_password() uses a constant-time comparison (bcrypt handles this).
    """
    # `form_data.username` holds the email — standard OAuth2 naming convention
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    # ── Verify credentials ─────────────────────────────────────────────────────
    # We call verify_password() even if user is None (using a dummy hash)
    # to avoid a timing side-channel where "user not found" returns faster
    # than "wrong password". The dummy hash ensures bcrypt always runs.
    DUMMY_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj40Nssm3yW2"
    password_ok = verify_password(
        form_data.password,
        user.hashed_password if user else DUMMY_HASH,
    )

    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Issue tokens ───────────────────────────────────────────────────────────
    # We store user.id (integer) as the JWT `sub` claim.
    # Why ID instead of email? IDs are immutable; emails can be changed.
    # Using an immutable identifier means tokens don't break if the user
    # updates their email.
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ── GET /auth/me ──────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the current authenticated user's profile",
)
async def get_me(current_user: CurrentUser) -> User:
    """
    Return the profile of the currently authenticated user.

    HOW THIS WORKS (the magic of dependency injection):
      `CurrentUser` is a type alias for `Annotated[User, Depends(get_current_user)]`.
      FastAPI sees the `Depends(get_current_user)` and runs that function first,
      which:
        1. Extracts the Bearer token from the Authorization header
        2. Decodes and validates the JWT
        3. Fetches the User from the database
        4. Injects the User object here as `current_user`

      By the time this function body runs, we ALREADY have the authenticated
      user — no additional code is needed. The route is literally one line.

    This demonstrates the power of FastAPI's dependency system: auth logic
    lives in one place (dependencies.py) and is reused across all protected
    routes without duplication.

    Returns:
      UserRead — the user's profile. Never includes the hashed_password field
      (UserRead schema simply doesn't have a `hashed_password` field).
    """
    return current_user
