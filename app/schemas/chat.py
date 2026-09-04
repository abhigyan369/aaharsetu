"""
app/schemas/chat.py — Pydantic Schemas for Real-time Chat
==========================================================
"""

from datetime import datetime
from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    channel_id: str = Field(default="global", max_length=50)
    message: str = Field(min_length=1, max_length=2000)


class ChatMessageOut(BaseModel):
    id: int
    sender_id: int
    sender_name: str
    sender_role: str
    channel_id: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
