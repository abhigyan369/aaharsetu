"""
app/schemas/connection.py — Pydantic Schemas for Connections
==============================================================
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.connection import ConnectionStatus
from app.schemas.user import UserPublic


class ConnectionCreate(BaseModel):
    peer_id: int = Field(..., description="ID of the user to connect with (must form a donor-receiver pair)")


class ConnectionUpdate(BaseModel):
    status: ConnectionStatus


class ConnectionRead(BaseModel):
    id: int
    requester_id: int
    addressee_id: int
    donor_id: int
    receiver_id: int
    status: ConnectionStatus
    created_at: datetime
    updated_at: datetime

    requester: UserPublic | None = None
    addressee: UserPublic | None = None
    donor: UserPublic | None = None
    receiver: UserPublic | None = None

    model_config = ConfigDict(from_attributes=True)


class ConnectionStatusResponse(BaseModel):
    status: str  # 'none', 'pending_sent', 'pending_received', 'accepted', 'declined'
    connection_id: int | None = None
