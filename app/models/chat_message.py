"""
app/models/chat_message.py — Chat Message ORM Model
===================================================

RELATIONSHIP SUMMARY:
  ChatMessage represents a single chat message sent by a User (donor, receiver, or admin)
  in a real-time unified chat channel.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    channel_id: Mapped[str] = mapped_column(
        String(50), default="global", nullable=False, index=True
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    sender: Mapped[User] = relationship("User", lazy="joined")

    __table_args__ = (
        Index("ix_chat_messages_channel_created", "channel_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} sender_id={self.sender_id} channel={self.channel_id!r}>"
