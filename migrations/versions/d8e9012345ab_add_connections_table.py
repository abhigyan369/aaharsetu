"""add_connections_table

Revision ID: d8e9012345ab
Revises: c7e3f89012ab
Create Date: 2026-09-05

WHAT THIS MIGRATION DOES:
  Creates the connections table to support donor-receiver connection requests
  and private chat authorization.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d8e9012345ab"
down_revision: str | None = "c7e3f89012ab"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Safely create ENUM type in Postgres if it doesn't already exist
    if conn.dialect.name == "postgresql":
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE connectionstatus AS ENUM ('pending', 'accepted', 'declined');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """
        )
        status_col_type = postgresql.ENUM(
            "pending", "accepted", "declined", name="connectionstatus", create_type=False
        )
    else:
        status_col_type = sa.Enum("pending", "accepted", "declined", name="connectionstatus")

    if "connections" not in tables:
        op.create_table(
            "connections",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("requester_id", sa.Integer(), nullable=False),
            sa.Column("addressee_id", sa.Integer(), nullable=False),
            sa.Column("donor_id", sa.Integer(), nullable=False),
            sa.Column("receiver_id", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                status_col_type,
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["addressee_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["donor_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("donor_id", "receiver_id", name="uq_donor_receiver_connection"),
        )
        op.create_index(op.f("ix_connections_id"), "connections", ["id"], unique=False)
        op.create_index(op.f("ix_connections_requester_id"), "connections", ["requester_id"], unique=False)
        op.create_index(op.f("ix_connections_addressee_id"), "connections", ["addressee_id"], unique=False)
        op.create_index(op.f("ix_connections_donor_id"), "connections", ["donor_id"], unique=False)
        op.create_index(op.f("ix_connections_receiver_id"), "connections", ["receiver_id"], unique=False)
        op.create_index("ix_connections_donor_status", "connections", ["donor_id", "status"], unique=False)
        op.create_index("ix_connections_receiver_status", "connections", ["receiver_id", "status"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "connections" in inspector.get_table_names():
        op.drop_index("ix_connections_receiver_status", table_name="connections")
        op.drop_index("ix_connections_donor_status", table_name="connections")
        op.drop_index(op.f("ix_connections_receiver_id"), table_name="connections")
        op.drop_index(op.f("ix_connections_donor_id"), table_name="connections")
        op.drop_index(op.f("ix_connections_addressee_id"), table_name="connections")
        op.drop_index(op.f("ix_connections_requester_id"), table_name="connections")
        op.drop_index(op.f("ix_connections_id"), table_name="connections")
        op.drop_table("connections")
        if conn.dialect.name == "postgresql":
            op.execute("DROP TYPE IF EXISTS connectionstatus;")
