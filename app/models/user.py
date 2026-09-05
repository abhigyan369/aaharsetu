"""
app/models/user.py — User ORM Model
=====================================

RELATIONSHIP SUMMARY (FK structure):
  User is the "parent" in two relationships:
    - User.listings      → one User (donor) can have many FoodListings
    - User.claims        → one User (receiver) can have many Claims
    - User.notifications → one User can have many Notifications

  This is a classic "one-to-many" pattern:
    users.id ←─ food_listings.donor_id
    users.id ←─ claims.receiver_id
    users.id ←─ notifications.user_id

INTERVIEW TALKING POINT:
  "I separated donor/receiver roles into a single User table with a role
  enum rather than two separate tables, because the fields are identical
  and a single table simplifies auth and future role changes. An admin
  can assign roles without schema changes."
"""

from __future__ import annotations  # must be first line — enables PEP 563 deferred annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    # These imports are ONLY evaluated by type checkers (mypy, Pylance), NOT at runtime.
    # At runtime, SQLAlchemy resolves the string "FoodListing" etc. lazily
    # during mapper configuration — so there is no circular import at runtime.
    from app.models.food_listing import FoodListing
    from app.models.claim import Claim
    from app.models.notification import Notification


# ── Enums ─────────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    """
    Using str as mixin means UserRole.DONOR == "donor" (True).
    This makes JSON serialisation trivial — no .value needed.
    """
    DONOR = "donor"
    RECEIVER = "receiver"
    ADMIN = "admin"


# ── Model ─────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── Core fields ──────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # unique=True creates a UNIQUE constraint in Postgres; index=True creates a
    # B-tree index so lookups by email are O(log n) instead of a full table scan.
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # NEVER store plain-text passwords — always store the bcrypt hash.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # SQLAlchemy maps Python enum → Postgres native ENUM type via the name= arg.
    # values_callable: use enum .value ("donor") not .name ("DONOR") — the Postgres
    # ENUM type was created with lowercase values matching UserRole.DONOR.value.
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.RECEIVER,
    )

    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Default Location (Donor pickup or Receiver location) ───────────────
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Email/phone verification flag — set to True after OTP/link verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # server_default=func.now() → Postgres fills this in at INSERT time.
    # We don't rely on Python's datetime.now() to avoid timezone confusion.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    # back_populates="donor" means FoodListing.donor is the other side of this link.
    # lazy="select" (default) — SQLAlchemy fetches related rows only when accessed.
    # For large lists, you'd switch to lazy="dynamic" or use selectinload() in queries.
    listings: Mapped[list[FoodListing]] = relationship(
        "FoodListing",
        back_populates="donor",
        cascade="all, delete-orphan",  # deleting a User deletes their listings too
        lazy="select",
    )

    claims: Mapped[list[Claim]] = relationship(
        "Claim",
        back_populates="receiver",
        cascade="all, delete-orphan",
        lazy="select",
    )

    notifications: Mapped[list[Notification]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ── Table-level constraints & indexes ─────────────────────────────────────
    __table_args__ = (
        # Composite index: quickly find all unverified donors, for example.
        Index("ix_users_role_verified", "role", "is_verified"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
