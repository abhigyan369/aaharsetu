"""add_chat_messages_table

Revision ID: c7e3f89012ab
Revises: bdacd13bdd41
Create Date: 2026-09-04

WHAT THIS MIGRATION DOES:
  Creates the chat_messages table to store real-time chat history for donors,
  receivers, and admins across channels (global, donor-receiver, admin-help).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ── Revision identifiers ──────────────────────────────────────────────────────
revision: str = "c7e3f89012ab"
down_revision: str | None = "bdacd13bdd41"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "chat_messages" in tables:
        # Table already exists — verify column schema compatibility
        existing_cols = {col["name"] for col in inspector.get_columns("chat_messages")}
        required_cols = {"id", "sender_id", "channel_id", "message", "created_at"}
        missing = required_cols - existing_cols
        if missing:
            raise RuntimeError(
                f"Table 'chat_messages' already exists but is missing required column(s): {missing}. "
                f"Manual database migration or resolution is required."
            )

        # Table exists and is compatible — create missing indexes if any
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("chat_messages")}
        if op.f("ix_chat_messages_id") not in existing_indexes:
            op.create_index(op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False)
        if op.f("ix_chat_messages_sender_id") not in existing_indexes:
            op.create_index(op.f("ix_chat_messages_sender_id"), "chat_messages", ["sender_id"], unique=False)
        if op.f("ix_chat_messages_channel_id") not in existing_indexes:
            op.create_index(op.f("ix_chat_messages_channel_id"), "chat_messages", ["channel_id"], unique=False)
        if "ix_chat_messages_channel_created" not in existing_indexes:
            op.create_index("ix_chat_messages_channel_created", "chat_messages", ["channel_id", "created_at"])
    else:
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("sender_id", sa.Integer(), nullable=False),
            sa.Column("channel_id", sa.String(length=50), nullable=False, server_default="global"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["sender_id"], ["users.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False)
        op.create_index(op.f("ix_chat_messages_sender_id"), "chat_messages", ["sender_id"], unique=False)
        op.create_index(op.f("ix_chat_messages_channel_id"), "chat_messages", ["channel_id"], unique=False)
        op.create_index("ix_chat_messages_channel_created", "chat_messages", ["channel_id", "created_at"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "chat_messages" in inspector.get_table_names():
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("chat_messages")}
        if "ix_chat_messages_channel_created" in existing_indexes:
            op.drop_index("ix_chat_messages_channel_created", table_name="chat_messages")
        if op.f("ix_chat_messages_channel_id") in existing_indexes:
            op.drop_index(op.f("ix_chat_messages_channel_id"), table_name="chat_messages")
        if op.f("ix_chat_messages_sender_id") in existing_indexes:
            op.drop_index(op.f("ix_chat_messages_sender_id"), table_name="chat_messages")
        if op.f("ix_chat_messages_id") in existing_indexes:
            op.drop_index(op.f("ix_chat_messages_id"), table_name="chat_messages")
        op.drop_table("chat_messages")
