"""
app/schemas/__init__.py
=======================

WHY THIS FOLDER EXISTS:
  Pydantic schemas (also called "data transfer objects" or DTOs) define
  the shape of data flowing IN and OUT of the API — request bodies,
  response bodies, and validation rules.

  They are SEPARATE from SQLAlchemy models on purpose:
    - SQLAlchemy model  → represents a database row
    - Pydantic schema   → represents data over the wire (HTTP)

  This separation lets you control exactly what gets exposed in the API
  (e.g., never expose `hashed_password` even if it's on the User model).
"""

# Re-export everything for convenient imports:
#   from app.schemas import UserRead, FoodListingCreate, ...
from app.schemas.user import UserBase, UserCreate, UserUpdate, UserRead, UserPublic
from app.schemas.food_listing import (
    FoodListingBase,
    FoodListingCreate,
    FoodListingUpdate,
    FoodListingRead,
    FoodListingSummary,
)
from app.schemas.claim import ClaimBase, ClaimCreate, ClaimUpdate, ClaimRead, ClaimSummary
from app.schemas.notification import NotificationRead, NotificationCreate, NotificationUpdate
from app.schemas.connection import ConnectionCreate, ConnectionUpdate, ConnectionRead, ConnectionStatusResponse

__all__ = [
    # User
    "UserBase", "UserCreate", "UserUpdate", "UserRead", "UserPublic",
    # FoodListing
    "FoodListingBase", "FoodListingCreate", "FoodListingUpdate",
    "FoodListingRead", "FoodListingSummary",
    # Claim
    "ClaimBase", "ClaimCreate", "ClaimUpdate", "ClaimRead", "ClaimSummary",
    # Notification
    "NotificationRead", "NotificationCreate", "NotificationUpdate",
    # Connection
    "ConnectionCreate", "ConnectionUpdate", "ConnectionRead", "ConnectionStatusResponse",
]

