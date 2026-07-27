"""
app/schemas/food_listing.py — Pydantic Schemas for FoodListing
===============================================================

NOTE ON GEOLOCATION:
  latitude/longitude are optional in Create so donors without GPS can still
  submit a text address. The haversine filter in Phase 4 simply skips listings
  with no coordinates when distance filtering is requested.

NOTE ON STATUS:
  Clients cannot set status directly on Create/Update — it's controlled by
  the application workflow (create=available, claim=claimed, pickup=picked_up).
  Only an admin-level endpoint would allow direct status override.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.food_listing import FoodType, ListingStatus
from app.schemas.user import UserPublic


# ── Base ──────────────────────────────────────────────────────────────────────
class FoodListingBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, examples=["Leftover biryani"])
    description: str | None = Field(None, examples=["Serves about 10 people, made today"])
    food_type: FoodType = Field(..., examples=[FoodType.COOKED])
    quantity: float = Field(..., gt=0, examples=[10.0])
    quantity_unit: str = Field(..., max_length=50, examples=["portions"])
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    address: str | None = Field(None, max_length=500, examples=["123 MG Road, Bengaluru"])
    pickup_window_start: datetime | None = None
    pickup_window_end: datetime | None = None
    expiry_time: datetime | None = None
    image_url: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def validate_pickup_window(self) -> "FoodListingBase":
        """
        Ensure pickup_window_end is after pickup_window_start if both are provided.
        model_validator runs after all field validators.
        """
        if (
            self.pickup_window_start is not None
            and self.pickup_window_end is not None
            and self.pickup_window_end <= self.pickup_window_start
        ):
            raise ValueError("pickup_window_end must be after pickup_window_start")
        return self


# ── Create ────────────────────────────────────────────────────────────────────
class FoodListingCreate(FoodListingBase):
    """
    Used in POST /listings (donor-only).
    donor_id is NOT here — it's taken from the authenticated user's JWT,
    never trusted from the request body.
    """
    pass


# ── Update ────────────────────────────────────────────────────────────────────
class FoodListingUpdate(BaseModel):
    """
    Used in PUT /listings/{id}.
    All optional — partial updates only.
    Status is excluded; use dedicated workflow endpoints instead.
    """

    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = None
    food_type: FoodType | None = None
    quantity: float | None = Field(None, gt=0)
    quantity_unit: str | None = Field(None, max_length=50)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    address: str | None = Field(None, max_length=500)
    pickup_window_start: datetime | None = None
    pickup_window_end: datetime | None = None
    expiry_time: datetime | None = None
    image_url: str | None = None


# ── Read ──────────────────────────────────────────────────────────────────────
class FoodListingRead(FoodListingBase):
    """Full listing returned in API responses, including nested donor info."""

    id: int
    donor_id: int
    status: ListingStatus
    created_at: datetime
    donor: UserPublic | None = None  # populated via selectinload in routes

    model_config = ConfigDict(from_attributes=True)


# ── Summary (for list views — avoids loading all fields) ──────────────────────
class FoodListingSummary(BaseModel):
    """Lightweight listing for list endpoints — avoids sending full description."""

    id: int
    title: str
    food_type: FoodType
    quantity: float
    quantity_unit: str
    address: str | None
    expiry_time: datetime | None
    status: ListingStatus
    image_url: str | None
    donor_id: int

    model_config = ConfigDict(from_attributes=True)
