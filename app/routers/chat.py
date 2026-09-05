"""
app/routers/chat.py — WebSocket Real-time Unified & Private Chat Router
========================================================================

Provides WebSocket real-time messaging and REST history retrieval
for Donors, Receivers, and Admins to interact in unified or private channels.
"""

import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token
from app.db.database import AsyncSessionLocal, get_db
from app.models.chat_message import ChatMessage
from app.models.connection import Connection, ConnectionStatus
from app.models.user import User
from app.schemas.chat import ChatMessageOut

router = APIRouter()


class ConnectionManager:
    """
    Manages active WebSocket connections across public and private chat channels.
    """

    def __init__(self):
        # Store dict mapping active WebSocket to user dict
        self.active_connections: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, user_info: dict):
        await websocket.accept()
        self.active_connections[websocket] = user_info

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, payload: dict, channel_id: Optional[str] = None):
        """
        Broadcast JSON payload to connected sockets.
        If channel_id starts with 'private_', sends ONLY to participants of that private chat.
        """
        target_user_ids = None
        if channel_id and channel_id.startswith("private_"):
            parts = channel_id.split("_")
            if len(parts) >= 3:
                try:
                    target_user_ids = {int(parts[1]), int(parts[2])}
                except ValueError:
                    pass

        disconnected = []
        for connection, uinfo in list(self.active_connections.items()):
            if target_user_ids is not None:
                if uinfo.get("id") not in target_user_ids:
                    continue  # Skip users not part of this private chat

            try:
                await connection.send_json(payload)
            except Exception:
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)


manager = ConnectionManager()


@router.get("/history", response_model=List[ChatMessageOut])
async def get_chat_history(
    channel_id: str = Query("global", max_length=50),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch historical chat messages for a specific channel.
    """
    stmt = (
        select(ChatMessage)
        .options(selectinload(ChatMessage.sender))
        .where(ChatMessage.channel_id == channel_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())
    messages.reverse()  # Oldest to newest for chat timeline display

    out = []
    for msg in messages:
        out.append(
            ChatMessageOut(
                id=msg.id,
                sender_id=msg.sender_id,
                sender_name=msg.sender.name if msg.sender else "Unknown",
                sender_role=msg.sender.role.value if msg.sender else "unknown",
                channel_id=msg.channel_id,
                message=msg.message,
                created_at=msg.created_at,
            )
        )
    return out


@router.websocket("/ws")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time unified & private chat.
    Requires token parameter for authentication: ws://.../chat/ws?token=<jwt_access_token>
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Authenticate user from database
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_info = {
        "id": user.id,
        "name": user.name,
        "role": user.role.value,
        "email": user.email,
    }

    await manager.connect(websocket, user_info)

    try:
        # Send connection confirmation payload
        await websocket.send_json(
            {
                "type": "connection_established",
                "user": user_info,
            }
        )

        while True:
            data_str = await websocket.receive_text()
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            message_text = data.get("message", "").strip()
            channel_id = data.get("channel_id", "global").strip() or "global"

            if not message_text:
                continue

            # Save message to DB
            async with AsyncSessionLocal() as db:
                chat_msg = ChatMessage(
                    sender_id=user.id,
                    channel_id=channel_id,
                    message=message_text,
                )
                db.add(chat_msg)
                await db.commit()
                await db.refresh(chat_msg)

                msg_payload = {
                    "type": "chat_message",
                    "data": {
                        "id": chat_msg.id,
                        "sender_id": user.id,
                        "sender_name": user.name,
                        "sender_role": user.role.value,
                        "channel_id": chat_msg.channel_id,
                        "message": chat_msg.message,
                        "created_at": chat_msg.created_at.isoformat(),
                    },
                }

            # Broadcast message to targeted sockets
            await manager.broadcast(msg_payload, channel_id=channel_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
