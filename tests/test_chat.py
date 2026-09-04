"""
tests/test_chat.py — Tests for Real-Time Chat WebSocket & History REST Endpoints
===================================================================================
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.user import User


@pytest.mark.asyncio
async def test_get_chat_history_empty(client: AsyncClient):
    """GET /chat/history returns empty list initially."""
    response = await client.get("/chat/history?channel_id=global")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_get_chat_history_with_messages(
    client: AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    db_session: AsyncSession,
):
    """GET /chat/history returns past chat messages with sender details."""
    user, token, headers = donor_user
    msg = ChatMessage(
        sender_id=user.id,
        channel_id="global",
        message="Hello community!",
    )
    db_session.add(msg)
    await db_session.commit()

    response = await client.get("/chat/history?channel_id=global")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["message"] == "Hello community!"
    assert data[0]["sender_id"] == user.id
    assert data[0]["sender_role"] == "donor"
