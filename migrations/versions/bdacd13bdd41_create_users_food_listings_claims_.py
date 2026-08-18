"""create_users_food_listings_claims_notifications

Revision ID: bdacd13bdd41
Revises:
Create Date: 2026-07-27

WHAT THIS MIGRATION DOES:
  Creates all four core tables from scratch:
    1. users          — authentication + role
    2. food_listings  — donated food items
    3. claims         — receiver claims on a listing
    4. notifications  — in-app alerts

  Also creates four PostgreSQL native ENUM types:
    - userrole        (donor, receiver, admin)
    - foodtype        (cooked, packaged, raw, bakery, other)
    - listingstatus   (available, claimed, picked_up, expired, cancelled)
    - claimstatus     (pending, confirmed, completed, cancelled)

HOW ALEMBIC USES THIS FILE:
  `alembic upgrade head`   → runs upgrade()
  `alembic downgrade -1`   → runs downgrade() (rolls back this migration)

  Both are committed to git so every developer and the production server
  runs exactly the same schema changes in the same order.

NOTE: This migration was hand-written because no live database was available
  during development. It exactly mirrors the SQLAlchemy model definitions.
  When you have a running Postgres instance, re-running:
    alembic revision --autogenerate -m "..."
  would produce an equivalent script automatically.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ──────────────────────────────────────────────────────
revision: str = "bdacd13bdd41"
down_revision: str | None = None  # This is the first migration (no parent)
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── Create ENUM types ─────────────────────────────────────────────────────
    # We create them explicitly so downgrade() can drop them cleanly.
    # SQLAlchemy would auto-create them on table creation, but explicit control
    # is better for rollback.
    userrole = sa.Enum("donor", "receiver", "admin", name="userrole")
    foodtype = sa.Enum("cooked", "packaged", "raw", "bakery", "other", name="foodtype")
    listingstatus = sa.Enum(
        "available", "claimed", "picked_up", "expired", "cancelled",
        name="listingstatus"
    )
    claimstatus = sa.Enum(
        "pending", "confirmed", "completed", "cancelled",
        name="claimstatus"
    )
    userrole.create(op.get_bind(), checkfirst=True)
    foodtype.create(op.get_bind(), checkfirst=True)
    listingstatus.create(op.get_bind(), checkfirst=True)
    claimstatus.create(op.get_bind(), checkfirst=True)

    # ── Table: users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("donor", "receiver", "admin", name="userrole", create_type=False),
            nullable=False,
        ),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Single-column indexes
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    # Composite index: role + is_verified (e.g. "find all unverified donors")
    op.create_index("ix_users_role_verified", "users", ["role", "is_verified"])

    # ── Table: food_listings ──────────────────────────────────────────────────
    op.create_table(
        "food_listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("donor_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "food_type",
            postgresql.ENUM("cooked", "packaged", "raw", "bakery", "other", name="foodtype", create_type=False),
            nullable=False,
        ),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("quantity_unit", sa.String(length=50), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("pickup_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "available", "claimed", "picked_up", "expired", "cancelled",
                name="listingstatus", create_type=False
            ),
            nullable=False,
            server_default="available",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["donor_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_food_listings_id"), "food_listings", ["id"], unique=False)
    op.create_index(op.f("ix_food_listings_donor_id"), "food_listings", ["donor_id"], unique=False)
    op.create_index(op.f("ix_food_listings_expiry_time"), "food_listings", ["expiry_time"], unique=False)
    op.create_index(op.f("ix_food_listings_status"), "food_listings", ["status"], unique=False)
    # Composite indexes
    op.create_index("ix_food_listings_status_expiry", "food_listings", ["status", "expiry_time"])
    op.create_index("ix_food_listings_lat_lon", "food_listings", ["latitude", "longitude"])
    op.create_index("ix_food_listings_donor_status", "food_listings", ["donor_id", "status"])

    # ── Table: claims ─────────────────────────────────────────────────────────
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "confirmed", "completed", "cancelled", name="claimstatus", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["food_listings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["receiver_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_claims_id"), "claims", ["id"], unique=False)
    op.create_index(op.f("ix_claims_listing_id"), "claims", ["listing_id"], unique=False)
    op.create_index(op.f("ix_claims_receiver_id"), "claims", ["receiver_id"], unique=False)
    op.create_index(op.f("ix_claims_status"), "claims", ["status"], unique=False)
    # Composite indexes
    op.create_index("ix_claims_listing_status", "claims", ["listing_id", "status"])
    op.create_index("ix_claims_receiver_status", "claims", ["receiver_id", "status"])

    # ── Table: notifications ──────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    # Composite: fetch all unread for a user
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])


def downgrade() -> None:
    # Drop tables in reverse dependency order (children before parents)
    op.drop_table("notifications")
    op.drop_table("claims")
    op.drop_table("food_listings")
    op.drop_table("users")

    # Drop ENUM types (Postgres doesn't auto-drop them when tables are dropped)
    sa.Enum(name="claimstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="listingstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="foodtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
