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
    op.drop_index("ix_chat_messages_channel_created", table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_channel_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_sender_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
