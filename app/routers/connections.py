"""
app/routers/connections.py — Donor-Receiver Connections Router
===============================================================

Handles friend-request-style connections between Donors and Receivers.
Enables either party to send connection requests, accept/decline them,
and view connected peers.
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.connection import Connection, ConnectionStatus
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.schemas.connection import ConnectionCreate, ConnectionRead, ConnectionStatusResponse

router = APIRouter()


@router.post(
    "/request",
    response_model=ConnectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a connection request to a donor or receiver",
)
async def send_connection_request(
    payload: ConnectionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectionRead:
    """
    Send a connection request to a peer user.
    Must be between a donor and a receiver (either direction).
    """
    if payload.peer_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot send a connection request to yourself.",
        )

    # Fetch peer user
    peer_res = await db.execute(select(User).where(User.id == payload.peer_id))
    peer_user = peer_res.scalar_one_or_none()

    if not peer_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {payload.peer_id} not found.",
        )

    # Verify donor-receiver pair
    roles = {current_user.role, peer_user.role}
    if UserRole.DONOR not in roles or UserRole.RECEIVER not in roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection requests must be between a donor and a receiver.",
        )

    # Determine donor_id and receiver_id
    if current_user.role == UserRole.DONOR:
        donor_id = current_user.id
        receiver_id = peer_user.id
    else:
        donor_id = peer_user.id
        receiver_id = current_user.id

    # Check for existing connection between this donor and receiver
    stmt = select(Connection).where(
        Connection.donor_id == donor_id,
        Connection.receiver_id == receiver_id,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        if existing.status == ConnectionStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You are already connected with this user.",
            )
        elif existing.status == ConnectionStatus.PENDING:
            if existing.requester_id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A connection request to this user is already pending.",
                )
            else:
                # If they already sent us a request, auto-accept it!
                existing.status = ConnectionStatus.ACCEPTED
                # Notify original requester
                notification = Notification(
                    user_id=existing.requester_id,
                    message=f"User {current_user.name} accepted your connection request!",
                )
                db.add(notification)
                await db.commit()
                await db.refresh(existing)
                return existing
        elif existing.status == ConnectionStatus.DECLINED:
            # Re-open connection request
            existing.requester_id = current_user.id
            existing.addressee_id = peer_user.id
            existing.status = ConnectionStatus.PENDING
            notification = Notification(
                user_id=peer_user.id,
                message=f"User {current_user.name} ({current_user.role.value}) sent you a connection request.",
            )
            db.add(notification)
            await db.commit()
            await db.refresh(existing)
            return existing

    # Create new connection request
    conn = Connection(
        requester_id=current_user.id,
        addressee_id=peer_user.id,
        donor_id=donor_id,
        receiver_id=receiver_id,
        status=ConnectionStatus.PENDING,
    )
    db.add(conn)

    # Notify addressee
    notification = Notification(
        user_id=peer_user.id,
        message=f"User {current_user.name} ({current_user.role.value}) sent you a connection request.",
    )
    db.add(notification)

    await db.commit()
    await db.refresh(conn)
    return conn


@router.post(
    "/{connection_id}/accept",
    response_model=ConnectionRead,
    summary="Accept a connection request",
)
async def accept_connection(
    connection_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectionRead:
    res = await db.execute(select(Connection).where(Connection.id == connection_id))
    conn = res.scalar_one_or_none()

    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found.",
        )

    if conn.addressee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the recipient of the connection request can accept it.",
        )

    conn.status = ConnectionStatus.ACCEPTED

    notification = Notification(
        user_id=conn.requester_id,
        message=f"User {current_user.name} accepted your connection request!",
    )
    db.add(notification)

    await db.commit()
    await db.refresh(conn)
    return conn


@router.post(
    "/{connection_id}/decline",
    response_model=ConnectionRead,
    summary="Decline or cancel a connection request",
)
async def decline_connection(
    connection_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectionRead:
    res = await db.execute(select(Connection).where(Connection.id == connection_id))
    conn = res.scalar_one_or_none()

    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found.",
        )

    if current_user.id not in (conn.requester_id, conn.addressee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this connection.",
        )

    conn.status = ConnectionStatus.DECLINED

    await db.commit()
    await db.refresh(conn)
    return conn


@router.get(
    "",
    response_model=List[ConnectionRead],
    summary="List all connections for the current user",
)
async def list_connections(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[ConnectionStatus] = Query(None),
) -> List[ConnectionRead]:
    stmt = (
        select(Connection)
        .options(
            selectinload(Connection.requester),
            selectinload(Connection.addressee),
            selectinload(Connection.donor),
            selectinload(Connection.receiver),
        )
        .where(
            or_(
                Connection.requester_id == current_user.id,
                Connection.addressee_id == current_user.id,
            )
        )
    )

    if status:
        stmt = stmt.where(Connection.status == status)

    stmt = stmt.order_by(Connection.updated_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get(
    "/status/{peer_id}",
    response_model=ConnectionStatusResponse,
    summary="Check connection status with a specific user",
)
async def get_connection_status_with_peer(
    peer_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectionStatusResponse:
    stmt = select(Connection).where(
        or_(
            (Connection.requester_id == current_user.id) & (Connection.addressee_id == peer_id),
            (Connection.requester_id == peer_id) & (Connection.addressee_id == current_user.id),
        )
    )
    res = await db.execute(stmt)
    conn = res.scalar_one_or_none()

    if not conn:
        return ConnectionStatusResponse(status="none", connection_id=None)

    if conn.status == ConnectionStatus.ACCEPTED:
        return ConnectionStatusResponse(status="accepted", connection_id=conn.id)
    elif conn.status == ConnectionStatus.DECLINED:
        return ConnectionStatusResponse(status="declined", connection_id=conn.id)
    elif conn.status == ConnectionStatus.PENDING:
        if conn.requester_id == current_user.id:
            return ConnectionStatusResponse(status="pending_sent", connection_id=conn.id)
        else:
            return ConnectionStatusResponse(status="pending_received", connection_id=conn.id)

    return ConnectionStatusResponse(status="none", connection_id=None)
