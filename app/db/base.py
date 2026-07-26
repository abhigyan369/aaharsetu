"""
app/db/base.py — SQLAlchemy Declarative Base
=============================================

WHY THIS FILE EXISTS:
  SQLAlchemy's "declarative" system lets you define database tables as Python
  classes. Every model class inherits from this `Base` — that's how SQLAlchemy
  knows to treat them as database tables.

  Alembic (the migration tool) also imports this `Base` to inspect which
  tables/columns exist and generate migration scripts automatically.

IMPORT ORDER MATTERS:
  When Alembic runs, it needs to see ALL model classes imported before it
  inspects `Base.metadata`. We collect those imports here so there's one
  reliable place to add new models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Any class that inherits from Base and defines a `__tablename__`
    becomes a database table automatically.

    Example (from Phase 2):
        class User(Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
    """
    pass


# ── Import all models here so Alembic can discover them ───────────────────────
# When you add a new model file in app/models/, add its import here.
# Example:
#   from app.models.user import User          # noqa: F401
#   from app.models.food_listing import FoodListing  # noqa: F401
