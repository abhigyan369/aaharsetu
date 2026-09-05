"""add_location_to_users_table

Revision ID: e8a9012345ef
Revises: d8e9012345ab
Create Date: 2026-09-05

WHAT THIS MIGRATION DOES:
  Adds latitude, longitude, and address columns to the users table to support
  persistent user locations for both Donors and Receivers.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e8a9012345ef"
down_revision: str | None = "d8e9012345ab"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("users")]

    if "latitude" not in columns:
        op.add_column("users", sa.Column("latitude", sa.Float(), nullable=True))
    if "longitude" not in columns:
        op.add_column("users", sa.Column("longitude", sa.Float(), nullable=True))
    if "address" not in columns:
        op.add_column("users", sa.Column("address", sa.String(length=500), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("users")]

    if "address" in columns:
        op.drop_column("users", "address")
    if "longitude" in columns:
        op.drop_column("users", "longitude")
    if "latitude" in columns:
        op.drop_column("users", "latitude")
