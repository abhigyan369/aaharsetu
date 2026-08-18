"""
tests/test_notifications.py — Notification Unit & Integration Tests
====================================================================

TESTS IN THIS MODULE:
  1. GET /notifications:
     - test_list_notifications_empty: Returns empty list for user with no notifications
     - test_list_notifications_returns_rows: Returns notifications created for user
     - test_list_notifications_unread_only: Filters unread notifications only

  2. GET /notifications/{id}/read:
     - test_mark_notification_read_success: Updates notification is_read to true
     - test_mark_notification_read_other_user_404: Returns 404 if notification belongs to another user
"""

import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_service import create_notification
from app.models.user import User


async def test_list_notifications_empty(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify listing notifications for user with no notifications returns empty list."""
    _, _, headers = donor_user
    response = await client.get("/notifications/", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_notifications_returns_rows(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    db_session: AsyncSession,
):
    """Verify notifications written to DB are returned for authenticated user."""
    user, _, headers = donor_user
    await create_notification(db_session, user.id, "Test Notification 1")
    await create_notification(db_session, user.id, "Test Notification 2")
    await db_session.commit()

    response = await client.get("/notifications/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    messages = {item["message"] for item in data}
    assert messages == {"Test Notification 1", "Test Notification 2"}


async def test_list_notifications_unread_only(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    db_session: AsyncSession,
):
    """Verify unread_only=true query param filters notifications correctly."""
    user, _, headers = donor_user
    n1 = await create_notification(db_session, user.id, "Unread Notif")
    n2 = await create_notification(db_session, user.id, "Read Notif")
    n2.is_read = True
    await db_session.commit()

    response = await client.get("/notifications/?unread_only=true", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == n1.id


async def test_mark_notification_read_success(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    db_session: AsyncSession,
):
    """Verify marking notification as read updates is_read to true."""
    user, _, headers = donor_user
    n = await create_notification(db_session, user.id, "Mark me read")
    await db_session.commit()

    response = await client.get(f"/notifications/{n.id}/read", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_read"] is True


async def test_mark_notification_read_other_user_404(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
    db_session: AsyncSession,
):
    """Verify trying to mark another user's notification as read returns 404."""
    donor, _, _ = donor_user
    _, _, receiver_headers = receiver_user
    n = await create_notification(db_session, donor.id, "Donor Notification")
    await db_session.commit()

    response = await client.get(f"/notifications/{n.id}/read", headers=receiver_headers)
    assert response.status_code == 404
