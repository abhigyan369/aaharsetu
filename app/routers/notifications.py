"""
app/routers/notifications.py — In-App Notification Endpoints
=============================================================

ENDPOINTS:
  GET  /notifications          — List current user's notifications (newest first)
  GET  /notifications/{id}/read — Mark a single notification as read

WHY GET FOR MARK-AS-READ (not PATCH)?
  Strictly speaking, mutating state with a GET request violates REST
  conventions (GET should be idempotent and safe — no side effects).
  The route is specified this way to match the Phase 4 prompt exactly.

  INTERVIEW TALKING POINT:
    "The /read endpoint uses GET as specified, but if I were designing this
    API independently I'd use PATCH /notifications/{id} with body
    {is_read: true}. GET for mutations breaks HTTP caching semantics —
    a caching proxy could serve a stale 200 without actually hitting the
    server, meaning the read state never gets updated. For a portfolio
    project it's fine; in production I'd use PATCH."

PAGINATION:
  GET /notifications supports limit/offset pagination to avoid returning
  huge payloads for users with many notifications.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.db.database import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationRead

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# GET /notifications — List current user's notifications
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=list[NotificationRead],
    summary="List current user's notifications (newest first)",
)
async def list_notifications(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    # ── Pagination ────────────────────────────────────────────────────────────
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Max notifications to return (default 20)")
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of notifications to skip")
    ] = 0,
    # ── Optional filter ───────────────────────────────────────────────────────
    unread_only: Annotated[
        bool,
        Query(description="If true, return only unread notifications")
    ] = False,
) -> list[NotificationRead]:
    """
    Return the authenticated user's notifications, newest first.

    **Filters:**
    - `unread_only=true` — return only notifications where `is_read=false`

    **Pagination:**
    - Default page size: 20, max: 100

    Notifications are system-generated (listing claimed, expiry warnings).
    They cannot be created or deleted via the API.
    """
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())  # newest first
    )

    if unread_only:
        query = query.where(Notification.is_read == False)  # noqa: E712

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return list(notifications)  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# GET /notifications/{id}/read — Mark a single notification as read
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark a notification as read",
)
async def mark_notification_read(
    notification_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationRead:
    """
    Mark the specified notification as read (`is_read = true`).

    **Authorization:** Users can only mark their own notifications as read.
    Attempting to mark another user's notification returns 404 (not 403),
    so we don't leak the existence of other users' notifications.

    **Idempotent:** Calling this on an already-read notification returns 200
    with the current state — no error.

    Note: This endpoint uses GET for mutations as specified. In a production
    API, PATCH /notifications/{id} would be the conventional choice.
    """
    # Fetch the notification, scoped to the current user (privacy: 404, not 403)
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,  # ownership check
        )
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        # Return 404 whether the notification doesn't exist OR belongs to
        # another user — prevents leaking which notification IDs exist.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found.",
        )

    # Idempotent: already read → return as-is without another DB write
    if not notification.is_read:
        notification.is_read = True
        await db.commit()
        await db.refresh(notification)

    return notification  # type: ignore[return-value]
