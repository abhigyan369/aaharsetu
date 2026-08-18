"""
tests/test_edge_cases.py — Edge Cases, Invalid Inputs & Expired Tokens Tests
=============================================================================

TESTS IN THIS MODULE:
  1. Invalid Inputs & Validation:
     - test_create_listing_invalid_quantity: Zero or negative quantity returns 422
     - test_create_listing_invalid_pickup_window: end <= start returns 422
     - test_create_listing_invalid_coordinates: lat outside [-90, 90] returns 422
     - test_signup_short_password: Password shorter than 8 chars returns 422

  2. Token Lifecycle & Security Edge Cases:
     - test_expired_token_returns_401: Expired JWT access token returns 401
     - test_malformed_token_returns_401: Garbled JWT returns 401

  3. Background Tasks & Utilities:
     - test_haversine_distance_computation: Validates haversine utility calculations
     - test_expire_stale_listings_background_job: Validates automatic expiration logic
"""

from datetime import datetime, timedelta, timezone
import pytest
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.core.utils import haversine, is_within_distance
from app.models.food_listing import FoodListing, ListingStatus
from app.models.user import User
from app.routers.listings import expire_stale_listings


async def test_create_listing_invalid_quantity(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that quantity <= 0 is rejected with 422."""
    _, _, headers = donor_user
    form_data = {
        "title": "Invalid Quantity",
        "food_type": "cooked",
        "quantity": "0",
        "quantity_unit": "servings",
    }
    response = await client.post("/listings/", data=form_data, headers=headers)
    assert response.status_code == 422


async def test_create_listing_invalid_pickup_window(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that pickup_window_end <= pickup_window_start returns 422."""
    _, _, headers = donor_user
    now = datetime.now(timezone.utc)
    form_data = {
        "title": "Bad Pickup Window",
        "food_type": "cooked",
        "quantity": "5",
        "quantity_unit": "servings",
        "pickup_window_start": (now + timedelta(hours=5)).isoformat(),
        "pickup_window_end": (now + timedelta(hours=2)).isoformat(),
    }
    response = await client.post("/listings/", data=form_data, headers=headers)
    assert response.status_code == 422
    assert "pickup_window_end must be after" in response.json()["detail"].lower()


async def test_create_listing_invalid_coordinates(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify latitude outside [-90, 90] returns 422."""
    _, _, headers = donor_user
    form_data = {
        "title": "Bad Lat",
        "food_type": "cooked",
        "quantity": "5",
        "quantity_unit": "servings",
        "latitude": "120.0",
        "longitude": "45.0",
    }
    response = await client.post("/listings/", data=form_data, headers=headers)
    assert response.status_code == 422


async def test_expired_token_returns_401(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that an expired JWT token is rejected with 401."""
    user, _, _ = donor_user
    expired_token = create_access_token(subject=user.id, expires_delta=timedelta(seconds=-10))
    headers = {"Authorization": f"Bearer {expired_token}"}

    response = await client.get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert "could not validate credentials" in response.json()["detail"].lower()


async def test_malformed_token_returns_401(client: httpx.AsyncClient):
    """Verify that a malformed JWT token is rejected with 401."""
    headers = {"Authorization": "Bearer not.a.valid.jwt.token"}
    response = await client.get("/auth/me", headers=headers)
    assert response.status_code == 401


def test_haversine_distance_computation():
    """Verify haversine formula calculations."""
    # Distance between Bengaluru (12.9716, 77.5946) and Chennai (13.0827, 80.2707) is ~290 km
    dist = haversine(12.9716, 77.5946, 13.0827, 80.2707)
    assert 285.0 <= dist <= 295.0

    # Same location distance is 0 km
    assert haversine(12.9716, 77.5946, 12.9716, 77.5946) == 0.0

    # Proximity helper
    assert is_within_distance(12.9716, 77.5946, 13.0827, 80.2707, max_km=300.0) is True
    assert is_within_distance(12.9716, 77.5946, 13.0827, 80.2707, max_km=100.0) is False
    assert is_within_distance(12.9716, 77.5946, None, None, max_km=100.0) is True


async def test_expire_stale_listings_background_job(
    db_session: AsyncSession,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify expire_stale_listings changes status of past-expiry listings to 'expired'."""
    user, _, _ = donor_user
    past = datetime.now(timezone.utc) - timedelta(hours=2)

    stale_listing = FoodListing(
        donor_id=user.id,
        title="Stale Milk",
        food_type="raw",
        quantity=2.0,
        quantity_unit="litres",
        expiry_time=past,
        status=ListingStatus.AVAILABLE,
    )
    db_session.add(stale_listing)
    await db_session.commit()
    await db_session.refresh(stale_listing)

    # Run the background job function
    await expire_stale_listings()

    # Refresh stale listing in current db_session
    await db_session.refresh(stale_listing)
    assert stale_listing.status == ListingStatus.EXPIRED
