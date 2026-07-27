"""
app/models/notification.py — Notification ORM Model
=====================================================

RELATIONSHIP SUMMARY:
  Simple one-to-many: one User has many Notifications.
  FK: notifications.user_id → users.id

  Notifications are created by the system (e.g., "Your listing was claimed!")
  and marked read by the user via GET /notifications/{id}/read (Phase 5).

DESIGN DECISION:
  We keep this intentionally simple — just a message string + is_read flag.
  In a production system you'd add a notification_type enum and a JSON
  payload field for structured data, but that's over-engineering for this phase.
"""

from __future__ import annotations  # must be first — enables PEP 563 deferred annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    __tablename__ = "notifications"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── Foreign Key ───────────────────────────────────────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Notification Payload ──────────────────────────────────────────────────
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # is_read defaults to False; the API endpoint flips it to True
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationship ──────────────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User",
        back_populates="notifications",
        lazy="select",
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    __table_args__ = (
        # Fetch all unread notifications for a user efficiently
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} user_id={self.user_id} "
            f"is_read={self.is_read}>"
        )
