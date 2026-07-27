"""
app/models/__init__.py
======================

WHY THIS FOLDER EXISTS:
  SQLAlchemy models live here. Each file defines one database table as a
  Python class. Importing them registers their tables with Base.metadata,
  which Alembic uses to autogenerate migration scripts.

CIRCULAR IMPORT SOLUTION:
  Individual model files import Base (from app.db.base) but NOT each other.
  Cross-model type hints use `TYPE_CHECKING` guards so they're only evaluated
  by type checkers — NOT at runtime. This file is the single safe place to
  import all models together (after Base is fully initialized).
"""

# Importing all models here registers their tables with Base.metadata.
# Alembic env.py and app/main.py both do `from app import models` or
# `import app.models` to trigger this file and make all tables visible.
from app.models.user import User                    # noqa: F401
from app.models.food_listing import FoodListing     # noqa: F401
from app.models.claim import Claim                  # noqa: F401
from app.models.notification import Notification    # noqa: F401

__all__ = ["User", "FoodListing", "Claim", "Notification"]
