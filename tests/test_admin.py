"""
tests/test_admin.py — Admin Analytics & Dashboard Tests
========================================================

TESTS IN THIS MODULE:
  1. GET /admin/stats (JSON API):
     - test_admin_stats_as_admin: Returns aggregated stats with 200 OK
     - test_admin_stats_as_donor_forbidden: Non-admin user gets 403 Forbidden
     - test_admin_stats_unauthenticated: Unauthenticated caller gets 401 Unauthorized

  2. GET /admin/dashboard (HTML Page):
     - test_admin_dashboard_html_as_admin: Renders admin dashboard HTML with 200 OK
     - test_admin_dashboard_html_as_receiver_forbidden: Non-admin receives 403 Forbidden
"""

import pytest
import httpx
from app.models.user import User


async def test_admin_stats_as_admin(
    client: httpx.AsyncClient,
    admin_user: tuple[User, str, dict[str, str]],
):
    """Verify that an admin can access GET /admin/stats and receives valid metrics."""
    _, _, headers = admin_user
    response = await client.get("/admin/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_listings" in data
    assert "active_listings" in data
    assert "completed_pickups" in data
    assert "total_donors" in data
    assert "total_receivers" in data
    assert "food_type_labels" in data
    assert "food_type_counts" in data
    assert "timeseries_labels" in data
    assert "timeseries_counts" in data


async def test_admin_stats_as_donor_forbidden(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that a non-admin user (donor) receives 403 Forbidden when calling /admin/stats."""
    _, _, headers = donor_user
    response = await client.get("/admin/stats", headers=headers)
    assert response.status_code == 403


async def test_admin_stats_unauthenticated(client: httpx.AsyncClient):
    """Verify that an unauthenticated caller receives 401 Unauthorized."""
    response = await client.get("/admin/stats")
    assert response.status_code == 401


async def test_admin_dashboard_html_as_admin(
    client: httpx.AsyncClient,
    admin_user: tuple[User, str, dict[str, str]],
):
    """Verify that GET /admin/dashboard returns 200 OK HTML for admin."""
    _, token, _ = admin_user
    cookies = {"access_token": token}
    response = await client.get("/admin/dashboard", cookies=cookies)
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "").lower()
    assert "Analytics Dashboard" in response.text or "AaharSetu" in response.text


async def test_admin_dashboard_html_as_receiver_forbidden(
    client: httpx.AsyncClient,
    receiver_user: tuple[User, str, dict[str, str]],
):
    """Verify that a receiver receives 403 Forbidden on /admin/dashboard."""
    _, token, _ = receiver_user
    cookies = {"access_token": token}
    response = await client.get("/admin/dashboard", cookies=cookies)
    assert response.status_code == 403
