"""
app/schemas/user.py — Pydantic Schemas for User
================================================

SCHEMA PATTERN EXPLAINED:
  We follow the "schema layering" pattern common in FastAPI projects:

    UserBase      → shared fields (used in Create + Read, never expose password)
    UserCreate    → extends Base, adds `password` (plain-text, only on input)
    UserUpdate    → all optional fields for PATCH requests
    UserRead      → extends Base, adds DB-generated fields (id, created_at)
                    — what we return to the client

  WHY NOT ONE SCHEMA?
    If we used a single schema, we'd either expose hashed_password in responses
    or have to add `exclude` everywhere. Separate schemas make the contract
    explicit and safe by design.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


# ── Base ──────────────────────────────────────────────────────────────────────
class UserBase(BaseModel):
    """Fields shared across all user schemas. Safe to expose in responses."""

    name: str = Field(..., min_length=1, max_length=100, examples=["Rahul Sharma"])
    email: EmailStr = Field(..., examples=["rahul@example.com"])
    phone: str | None = Field(None, max_length=20, examples=["+91-9876543210"])
    role: UserRole = Field(UserRole.RECEIVER, examples=[UserRole.DONOR])


# ── Create ────────────────────────────────────────────────────────────────────
class UserCreate(UserBase):
    """
    Used in POST /auth/signup.
    Contains plain-text password — ONLY ever received from the client,
    never stored or returned.
    """

    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        examples=["Str0ngP@ss!"],
        description="Plain-text password; will be hashed before storage.",
    )


# ── Update ────────────────────────────────────────────────────────────────────
class UserUpdate(BaseModel):
    """
    Used in PATCH /users/{id}.
    All fields are optional — only provided fields are updated.
    Password change handled by a separate dedicated endpoint for clarity.
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=20)
    is_verified: bool | None = None


# ── Read ──────────────────────────────────────────────────────────────────────
class UserRead(UserBase):
    """
    Returned in API responses. Never includes hashed_password.

    model_config = ConfigDict(from_attributes=True) allows Pydantic to read
    data directly from a SQLAlchemy ORM object (instead of requiring a dict).
    Without this, `UserRead.model_validate(db_user)` would fail.
    """

    id: int
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Public profile (minimal, for display in listings) ─────────────────────────
class UserPublic(BaseModel):
    """Minimal user info embedded in FoodListingRead responses."""

    id: int
    name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)
