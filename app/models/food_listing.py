"""
app/models/food_listing.py — FoodListing ORM Model
====================================================

RELATIONSHIP SUMMARY:
  FoodListing sits in the middle of the graph:
    - FoodListing.donor  → Many-to-one back to User (the donor who posted it)
    - FoodListing.claims → One FoodListing can have many Claims
                           (only one should be "confirmed" at a time — enforced
                           at application level via a DB transaction in Phase 4)

  FK structure:
    food_listings.donor_id → users.id   (who posted the food)
    claims.listing_id      → food_listings.id  (who claimed it)

GEOSPATIAL NOTE:
  We store latitude/longitude as plain Float columns for now. For production
  with heavy geo queries you'd add PostGIS and use geography types. For this
  scale, the haversine formula computed in Python (Phase 4) is sufficient.
"""

from __future__ import annotations  # must be first — enables PEP 563 deferred annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.claim import Claim


# ── Enums ─────────────────────────────────────────────────────────────────────
class FoodType(str, enum.Enum):
    COOKED = "cooked"
    PACKAGED = "packaged"
    RAW = "raw"
    BAKERY = "bakery"
    OTHER = "other"


class ListingStatus(str, enum.Enum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    PICKED_UP = "picked_up"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ── Model ─────────────────────────────────────────────────────────────────────
class FoodListing(Base):
    __tablename__ = "food_listings"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── Foreign Key ───────────────────────────────────────────────────────────
    # ondelete="CASCADE" means if the donor User is deleted, their listings
    # are deleted too — consistent with the relationship(cascade=) on the Python side.
    donor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Listing Details ───────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    food_type: Mapped[FoodType] = mapped_column(
        Enum(FoodType, name="foodtype"), nullable=False
    )

    # quantity is a number (e.g. 5) and quantity_unit is the unit (e.g. "kg", "portions")
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # ── Location ──────────────────────────────────────────────────────────────
    # Latitude range: -90 to 90; Longitude range: -180 to 180
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Timing ────────────────────────────────────────────────────────────────
    # pickup_window_start/end: the time range when the donor is available for pickup
    pickup_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pickup_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # expiry_time: when the food goes bad — used by the background job that
    # auto-expires listings. Indexed because we query "WHERE expiry_time < NOW()"
    # frequently.
    expiry_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ── Media ─────────────────────────────────────────────────────────────────
    # Cloudinary URL added in Phase 6; nullable because upload is optional
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, name="listingstatus"),
        nullable=False,
        default=ListingStatus.AVAILABLE,
        index=True,  # We query by status very often (e.g. "all available listings")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    donor: Mapped[User] = relationship(
        "User",
        back_populates="listings",
        lazy="select",
    )

    claims: Mapped[list[Claim]] = relationship(
        "Claim",
        back_populates="listing",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ── Composite Indexes ─────────────────────────────────────────────────────
    __table_args__ = (
        # Filter available listings that haven't expired + nearby (lat/lon)
        Index("ix_food_listings_status_expiry", "status", "expiry_time"),
        # Spatial bounding-box pre-filter before haversine calculation
        Index("ix_food_listings_lat_lon", "latitude", "longitude"),
        # All listings by a specific donor
        Index("ix_food_listings_donor_status", "donor_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<FoodListing id={self.id} title={self.title!r} status={self.status}>"
