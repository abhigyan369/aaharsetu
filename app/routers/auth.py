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
from sqlalchemy.exc import IntegrityError
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
from app.schemas.user import UserCreate, UserRead, UserUpdate

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
    """
    if user_in.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Admin accounts cannot be created via self-signup. "
                "Contact a system administrator."
            ),
        )

    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    hashed = hash_password(user_in.password)

    new_user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hashed,
        role=user_in.role,
        phone=user_in.phone,
        latitude=user_in.latitude,
        longitude=user_in.longitude,
        address=user_in.address,
        is_verified=False,
    )

    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
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
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

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
    return current_user


# ── PUT /auth/me ──────────────────────────────────────────────────────────────
@router.put(
    "/me",
    response_model=UserRead,
    summary="Update the current authenticated user's profile and location",
)
async def update_me(
    payload: UserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Update profile fields (name, phone, address, latitude, longitude) for current user.
    """
    if payload.name is not None:
        current_user.name = payload.name
    if payload.phone is not None:
        current_user.phone = payload.phone
    if payload.latitude is not None:
        current_user.latitude = payload.latitude
    if payload.longitude is not None:
        current_user.longitude = payload.longitude
    if payload.address is not None:
        current_user.address = payload.address

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user

