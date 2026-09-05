"""
app/models/connection.py — Connection ORM Model
=================================================

RELATIONSHIP SUMMARY:
  Connection represents a friend-request-style link between a Donor and a Receiver.
  Either party can initiate the request, and the addressee accepts or declines it.

  FK structure:
    connections.requester_id → users.id (who sent request)
    connections.addressee_id → users.id (who receives request)
    connections.donor_id     → users.id (the donor in this pair)
    connections.receiver_id  → users.id (the receiver in this pair)
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ConnectionStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    addressee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    donor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connectionstatus", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ConnectionStatus.PENDING,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    requester: Mapped[User] = relationship("User", foreign_keys=[requester_id], lazy="joined")
    addressee: Mapped[User] = relationship("User", foreign_keys=[addressee_id], lazy="joined")
    donor: Mapped[User] = relationship("User", foreign_keys=[donor_id], lazy="joined")
    receiver: Mapped[User] = relationship("User", foreign_keys=[receiver_id], lazy="joined")

    __table_args__ = (
        UniqueConstraint("donor_id", "receiver_id", name="uq_donor_receiver_connection"),
        Index("ix_connections_donor_status", "donor_id", "status"),
        Index("ix_connections_receiver_status", "receiver_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Connection id={self.id} donor_id={self.donor_id} "
            f"receiver_id={self.receiver_id} status={self.status}>"
        )
