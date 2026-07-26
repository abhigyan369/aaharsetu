"""
app/models/__init__.py
======================

WHY THIS FOLDER EXISTS:
  SQLAlchemy models live here. Each file in this folder defines one
  database table as a Python class (e.g., models/user.py → users table).

  Planned models (Phase 2):
    - user.py          → User (auth + roles)
    - food_listing.py  → FoodListing (donated food items)
    - claim.py         → Claim (receiver claims a listing)
    - notification.py  → Notification (in-app alerts)
"""
