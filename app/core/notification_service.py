"""
app/core/notification_service.py — Notification DB Write Helper
================================================================

WHY THIS FILE EXISTS:
  The same "create a Notification row" logic is needed in two places:
    1. app/routers/listings.py — when a listing is claimed
    2. app/core/scheduler.py   — when a listing is about to expire

  Rather than copy-pasting the ORM code, we centralise it here.
  This is the Single Responsibility Principle applied: the router handles
  HTTP concerns, the scheduler handles timing concerns, and this module
  handles notification persistence.

DESIGN DECISION — why not use a schema for the internal call?
  NotificationCreate (Pydantic schema) exists but is only needed if you
  expose a creation endpoint. Internally, passing (db, user_id, message)
  directly is cleaner — fewer indirections, no serialization overhead.

STORE-THEN-SEND PATTERN:
  This function ONLY writes the DB row. The caller is responsible for
  sending the email afterward (via email_service.send_email). This means:
    - The notification is always persisted, even if email delivery fails.
    - The DB write and email send can be separated (e.g., email as a
      BackgroundTask, DB write inline in the request).
    - In-app notification list always has complete data.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    user_id: int,
    message: str,
) -> Notification:
    """
    Persist a Notification row for the given user.

    This is an internal helper — notifications are never created directly
    by API clients. They are always system-generated (claim events,
    expiry warnings, etc.).

    The caller is responsible for committing the session if not using
    auto-commit. In practice:
      - When called from a route handler: the route's `db` session will
        be committed at the end of the request (or we can commit here).
      - When called from the scheduler: the scheduler uses its own session
        with explicit commit.

    We commit inside this function so it works correctly in both contexts
    (the scheduler passes its own session; the route may or may not have
    committed already).

    Args:
        db:       An active async SQLAlchemy session.
        user_id:  The ID of the user who should receive this notification.
        message:  The human-readable notification message.

    Returns:
        The newly created (and committed) Notification ORM instance.
    """
    notification = Notification(user_id=user_id, message=message)
    db.add(notification)
    await db.flush()   # Write to DB within the current transaction but don't
                       # commit yet — lets the caller control the commit boundary.
                       # If the caller's transaction rolls back, this row rolls back too.
    await db.refresh(notification)  # Populate server-side defaults (id, created_at)

    logger.info(
        "Created notification id=%s for user_id=%s: %r",
        notification.id,
        user_id,
        message[:60],  # log first 60 chars to avoid huge log lines
    )
    return notification
