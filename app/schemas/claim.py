"""
app/schemas/claim.py — Pydantic Schemas for Claim
==================================================

NOTE ON RECEIVER_ID:
  receiver_id is never in ClaimCreate — it comes from the JWT token.
  This prevents a receiver from impersonating another user by sending
  a different receiver_id in the request body.

NOTE ON STATUS IN CREATE:
  status is also excluded from ClaimCreate — every new claim starts as
  PENDING. Status changes happen via dedicated endpoints (confirm, complete,
  cancel) rather than free-form PATCH to prevent invalid state transitions.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.claim import ClaimStatus
from app.schemas.user import UserPublic


# ── Base ──────────────────────────────────────────────────────────────────────
class ClaimBase(BaseModel):
    notes: str | None = Field(
        None,
        max_length=1000,
        examples=["I'll arrive at 6 PM. Please keep it warm."],
    )


# ── Create ────────────────────────────────────────────────────────────────────
class ClaimCreate(ClaimBase):
    """
    Used in POST /listings/{id}/claim.
    listing_id comes from the URL path param, receiver_id from JWT.
    Only `notes` is accepted from the request body.
    """
    pass


# ── Update ────────────────────────────────────────────────────────────────────
class ClaimUpdate(BaseModel):
    """
    For admin use or future PATCH endpoint.
    In practice, status transitions use dedicated action endpoints.
    """

    status: ClaimStatus | None = None
    notes: str | None = Field(None, max_length=1000)


# ── Read ──────────────────────────────────────────────────────────────────────
class ClaimRead(ClaimBase):
    """Full claim response including relationships."""

    id: int
    listing_id: int
    receiver_id: int
    claimed_at: datetime
    status: ClaimStatus
    receiver: UserPublic | None = None  # populated via selectinload

    model_config = ConfigDict(from_attributes=True)


# ── Summary ───────────────────────────────────────────────────────────────────
class ClaimSummary(BaseModel):
    """Minimal claim info for embedding in FoodListingRead."""

    id: int
    receiver_id: int
    claimed_at: datetime
    status: ClaimStatus

    model_config = ConfigDict(from_attributes=True)
