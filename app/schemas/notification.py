"""
app/schemas/notification.py — Pydantic Schemas for Notification
================================================================

Notifications are system-generated; the API only needs:
  - Read schema (what to return to the client)
  - No Create schema exposed to clients — notifications are created
    internally by the application (e.g., when a claim is made)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Read ──────────────────────────────────────────────────────────────────────
class NotificationRead(BaseModel):
    """Returned by GET /notifications."""

    id: int
    user_id: int
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Internal Create (used by application code, not exposed as an endpoint) ────
class NotificationCreate(BaseModel):
    """
    Used internally when the app creates a notification (e.g., in a background task).
    user_id is passed directly by the calling code — no auth context needed
    since this is a server-side operation.
    """

    user_id: int
    message: str


# ── Update ────────────────────────────────────────────────────────────────────
class NotificationUpdate(BaseModel):
    """Used by GET /notifications/{id}/read to mark as read."""

    is_read: bool = True
