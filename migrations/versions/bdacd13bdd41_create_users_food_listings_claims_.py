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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # ── Create ENUM types ─────────────────────────────────────────────────────
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
    userrole.create(conn, checkfirst=True)
    foodtype.create(conn, checkfirst=True)
    listingstatus.create(conn, checkfirst=True)
    claimstatus.create(conn, checkfirst=True)

    # ── Table: users ─────────────────────────────────────────────────────────
    if "users" in tables:
        existing_cols = {col["name"] for col in inspector.get_columns("users")}
        required_cols = {"id", "name", "email", "hashed_password", "role", "phone", "is_verified", "created_at"}
        missing = required_cols - existing_cols
        if missing:
            raise RuntimeError(f"Table 'users' already exists but is missing required column(s): {missing}.")
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("users")}
        if op.f("ix_users_id") not in existing_indexes:
            op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
        if op.f("ix_users_email") not in existing_indexes:
            op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
        if "ix_users_role_verified" not in existing_indexes:
            op.create_index("ix_users_role_verified", "users", ["role", "is_verified"])
    else:
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
        op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
        op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
        op.create_index("ix_users_role_verified", "users", ["role", "is_verified"])

    # ── Table: food_listings ──────────────────────────────────────────────────
    if "food_listings" in tables:
        existing_cols = {col["name"] for col in inspector.get_columns("food_listings")}
        required_cols = {"id", "donor_id", "title", "description", "food_type", "quantity", "quantity_unit", "status", "created_at"}
        missing = required_cols - existing_cols
        if missing:
            raise RuntimeError(f"Table 'food_listings' already exists but is missing required column(s): {missing}.")
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("food_listings")}
        if op.f("ix_food_listings_id") not in existing_indexes:
            op.create_index(op.f("ix_food_listings_id"), "food_listings", ["id"], unique=False)
        if op.f("ix_food_listings_donor_id") not in existing_indexes:
            op.create_index(op.f("ix_food_listings_donor_id"), "food_listings", ["donor_id"], unique=False)
        if op.f("ix_food_listings_expiry_time") not in existing_indexes:
            op.create_index(op.f("ix_food_listings_expiry_time"), "food_listings", ["expiry_time"], unique=False)
        if op.f("ix_food_listings_status") not in existing_indexes:
            op.create_index(op.f("ix_food_listings_status"), "food_listings", ["status"], unique=False)
        if "ix_food_listings_status_expiry" not in existing_indexes:
            op.create_index("ix_food_listings_status_expiry", "food_listings", ["status", "expiry_time"])
        if "ix_food_listings_lat_lon" not in existing_indexes:
            op.create_index("ix_food_listings_lat_lon", "food_listings", ["latitude", "longitude"])
        if "ix_food_listings_donor_status" not in existing_indexes:
            op.create_index("ix_food_listings_donor_status", "food_listings", ["donor_id", "status"])
    else:
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
        op.create_index("ix_food_listings_status_expiry", "food_listings", ["status", "expiry_time"])
        op.create_index("ix_food_listings_lat_lon", "food_listings", ["latitude", "longitude"])
        op.create_index("ix_food_listings_donor_status", "food_listings", ["donor_id", "status"])

    # ── Table: claims ─────────────────────────────────────────────────────────
    if "claims" in tables:
        existing_cols = {col["name"] for col in inspector.get_columns("claims")}
        required_cols = {"id", "listing_id", "receiver_id", "claimed_at", "status"}
        missing = required_cols - existing_cols
        if missing:
            raise RuntimeError(f"Table 'claims' already exists but is missing required column(s): {missing}.")
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("claims")}
        if op.f("ix_claims_id") not in existing_indexes:
            op.create_index(op.f("ix_claims_id"), "claims", ["id"], unique=False)
        if op.f("ix_claims_listing_id") not in existing_indexes:
            op.create_index(op.f("ix_claims_listing_id"), "claims", ["listing_id"], unique=False)
        if op.f("ix_claims_receiver_id") not in existing_indexes:
            op.create_index(op.f("ix_claims_receiver_id"), "claims", ["receiver_id"], unique=False)
        if op.f("ix_claims_status") not in existing_indexes:
            op.create_index(op.f("ix_claims_status"), "claims", ["status"], unique=False)
        if "ix_claims_listing_status" not in existing_indexes:
            op.create_index("ix_claims_listing_status", "claims", ["listing_id", "status"])
        if "ix_claims_receiver_status" not in existing_indexes:
            op.create_index("ix_claims_receiver_status", "claims", ["receiver_id", "status"])
    else:
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
        op.create_index("ix_claims_listing_status", "claims", ["listing_id", "status"])
        op.create_index("ix_claims_receiver_status", "claims", ["receiver_id", "status"])

    # ── Table: notifications ──────────────────────────────────────────────────
    if "notifications" in tables:
        existing_cols = {col["name"] for col in inspector.get_columns("notifications")}
        required_cols = {"id", "user_id", "message", "is_read", "created_at"}
        missing = required_cols - existing_cols
        if missing:
            raise RuntimeError(f"Table 'notifications' already exists but is missing required column(s): {missing}.")
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("notifications")}
        if op.f("ix_notifications_id") not in existing_indexes:
            op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
        if op.f("ix_notifications_user_id") not in existing_indexes:
            op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
        if "ix_notifications_user_read" not in existing_indexes:
            op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])
    else:
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
        op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    for table in ["notifications", "claims", "food_listings", "users"]:
        if table in tables:
            op.drop_table(table)

    sa.Enum(name="claimstatus").drop(conn, checkfirst=True)
    sa.Enum(name="listingstatus").drop(conn, checkfirst=True)
    sa.Enum(name="foodtype").drop(conn, checkfirst=True)
    sa.Enum(name="userrole").drop(conn, checkfirst=True)
