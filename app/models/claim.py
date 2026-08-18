"""
app/models/claim.py — Claim ORM Model
=======================================

RELATIONSHIP SUMMARY:
  Claim is the "join" between a FoodListing and a receiver User.
  It represents a receiver saying "I want this food".

  FK structure:
    claims.listing_id  → food_listings.id  (which listing was claimed)
    claims.receiver_id → users.id          (who claimed it)

  This is a many-to-many bridge made explicit:
    One FoodListing can be claimed by multiple users at different times
    (e.g. if the first claim is cancelled, another receiver can claim it).
    But only ONE claim should be active (pending/confirmed) at any time —
    enforced in Phase 4 with a SELECT FOR UPDATE transaction.

INTERVIEW TALKING POINT:
  "We prevent double-claiming with a database-level transaction:
  SELECT the listing with FOR UPDATE (row lock), check the status,
  then INSERT the claim — all in one atomic block. No two requests
  can hold the lock simultaneously."
"""

from __future__ import annotations  # must be first — enables PEP 563 deferred annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.food_listing import FoodListing
    from app.models.user import User


# ── Enum ──────────────────────────────────────────────────────────────────────
class ClaimStatus(str, enum.Enum):
    PENDING = "pending"        # Receiver has claimed, donor hasn't confirmed yet
    CONFIRMED = "confirmed"    # Donor acknowledged the claim
    COMPLETED = "completed"    # Food was physically picked up
    CANCELLED = "cancelled"    # Either party cancelled


# ── Model ─────────────────────────────────────────────────────────────────────
class Claim(Base):
    __tablename__ = "claims"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── Foreign Keys ──────────────────────────────────────────────────────────
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("food_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Claim Fields ──────────────────────────────────────────────────────────
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, name="claimstatus", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ClaimStatus.PENDING,
        index=True,
    )

    # Optional message from the receiver to the donor
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    listing: Mapped[FoodListing] = relationship(
        "FoodListing",
        back_populates="claims",
        lazy="select",
    )

    receiver: Mapped[User] = relationship(
        "User",
        back_populates="claims",
        lazy="select",
    )

    # ── Composite Indexes ─────────────────────────────────────────────────────
    __table_args__ = (
        # Check all claims for a listing quickly (e.g. "is there an active claim?")
        Index("ix_claims_listing_status", "listing_id", "status"),
        # All claims by a receiver (for their dashboard)
        Index("ix_claims_receiver_status", "receiver_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Claim id={self.id} listing_id={self.listing_id} "
            f"receiver_id={self.receiver_id} status={self.status}>"
        )
