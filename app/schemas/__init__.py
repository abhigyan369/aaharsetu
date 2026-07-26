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

  Planned schemas (Phase 2):
    - user.py          → UserBase, UserCreate, UserRead, UserUpdate
    - food_listing.py  → FoodListingBase, FoodListingCreate, FoodListingRead, etc.
    - claim.py         → ClaimCreate, ClaimRead, etc.
    - token.py         → Token, TokenData (JWT response shapes)
"""
