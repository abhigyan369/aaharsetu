"""
tests/test_listings.py — Food Listings & Claims Lifecycle Tests
================================================================

TESTS IN THIS MODULE:
  1. Creation & Role Enforcement:
     - test_create_listing_donor_success: Donor creates listing (201 Created, status='available')
     - test_create_listing_rejected_for_receiver: Receiver gets 403 Forbidden
     - test_create_listing_unauthenticated: Unauthenticated caller gets 401 Unauthorized

  2. Listing Retrieval & Filtering:
     - test_list_listings_public: Public access without token
     - test_list_listings_filter_food_type_and_status: Filtering by food_type and status
     - test_list_listings_proximity_filter: Filtering by coordinates and max_distance_km
     - test_get_listing_by_id_success: Retrieve single listing detail
     - test_get_listing_not_found: Querying non-existent ID returns 404

  3. Claim Flow & Race Condition Prevention:
     - test_claim_listing_receiver_success: Receiver claims available listing (status -> 'claimed')
     - test_claim_listing_prevent_double_claim: Second claim attempt returns 409 Conflict
     - test_claim_listing_rejected_for_donor: Donor cannot claim listings (403 Forbidden)
     - test_claim_listing_unauthenticated: Unauthenticated caller gets 401

  4. Permissions & Edit/Delete Guards:
     - test_update_listing_owner_donor_success: Owner donor edits available listing (PUT /listings/{id})
     - test_update_listing_forbidden_for_other_donor: Non-owner donor gets 403 Forbidden
     - test_update_listing_forbidden_when_claimed: Editing a claimed listing returns 400 Bad Request
     - test_cancel_listing_soft_delete: Owner donor soft-deletes listing (DELETE /listings/{id} -> status='cancelled')
     - test_cancel_listing_forbidden_for_other_donor: Non-owner gets 403 Forbidden

  5. Completion Flow (Pickup):
     - test_complete_listing_by_donor: Donor marks claimed listing as picked_up / completed
     - test_complete_listing_by_receiver: Receiver marks claimed listing as picked_up / completed
     - test_complete_listing_unauthorized_user: Unrelated user gets 403 Forbidden
"""

from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim, ClaimStatus
from app.models.food_listing import FoodListing, FoodType, ListingStatus
from app.models.notification import Notification
from app.models.user import User


# ── Helper to create a listing directly or via API ────────────────────────────
async def _create_sample_listing(
    client: httpx.AsyncClient,
    donor_headers: dict[str, str],
    title: str = "Fresh Sourdough Bread",
    food_type: str = "bakery",
    quantity: float = 10.0,
    quantity_unit: str = "loaves",
    latitude: float = 40.7128,
    longitude: float = -74.0060,
    address: str = "123 Main St, New York, NY",
) -> dict:
    """Helper to create a food listing via the multipart/form-data endpoint."""
    expiry = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    pickup_start = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    pickup_end = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()

    form_data = {
        "title": title,
        "food_type": food_type,
        "quantity": str(quantity),
        "quantity_unit": quantity_unit,
        "latitude": str(latitude),
        "longitude": str(longitude),
        "address": address,
        "expiry_time": expiry,
        "pickup_window_start": pickup_start,
        "pickup_window_end": pickup_end,
    }
    response = await client.post("/listings/", data=form_data, headers=donor_headers)
    assert response.status_code == 201, f"Failed to create listing: {response.text}"
    return response.json()


# ── 1. Creation & Role Enforcement Tests ──────────────────────────────────────
async def test_create_listing_donor_success(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that a donor can create a food listing with default status 'available'."""
    user, _, headers = donor_user
    listing_data = await _create_sample_listing(client, headers, title="Surplus Apples")

    assert listing_data["title"] == "Surplus Apples"
    assert listing_data["status"] == "available"
    assert listing_data["donor_id"] == user.id
    assert listing_data["donor"]["name"] == user.name
    assert "image_url" in listing_data
    assert listing_data["image_url"] is not None


async def test_create_listing_rejected_for_receiver(
    client: httpx.AsyncClient,
    receiver_user: tuple[User, str, dict[str, str]],
):
    """Verify that receivers cannot create listings (403 Forbidden)."""
    _, _, headers = receiver_user
    form_data = {
        "title": "Receiver Attempt",
        "food_type": "cooked",
        "quantity": "5",
        "quantity_unit": "meals",
    }
    response = await client.post("/listings/", data=form_data, headers=headers)
    assert response.status_code == 403
    assert "access denied" in response.json()["detail"].lower()


async def test_create_listing_unauthenticated(client: httpx.AsyncClient):
    """Verify that unauthenticated requests to create listings return 401."""
    form_data = {
        "title": "Anonymous Food",
        "food_type": "raw",
        "quantity": "2",
        "quantity_unit": "kg",
    }
    response = await client.post("/listings/", data=form_data)
    assert response.status_code == 401


# ── 2. Retrieval & Filtering Tests ────────────────────────────────────────────
async def test_list_listings_public(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that listing discovery is public (no auth required) and paginated."""
    _, _, headers = donor_user
    await _create_sample_listing(client, headers, title="Public Item 1")
    await _create_sample_listing(client, headers, title="Public Item 2")

    response = await client.get("/listings/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


async def test_list_listings_filter_food_type_and_status(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify filtering by food_type and status."""
    _, _, headers = donor_user
    await _create_sample_listing(client, headers, title="Bakery Item", food_type="bakery")
    await _create_sample_listing(client, headers, title="Cooked Stew", food_type="cooked")

    # Filter bakery only
    res_bakery = await client.get("/listings/?food_type=bakery&status=available")
    assert res_bakery.status_code == 200
    bakery_items = res_bakery.json()["items"]
    assert all(item["food_type"] == "bakery" for item in bakery_items)
    assert any(item["title"] == "Bakery Item" for item in bakery_items)


async def test_list_listings_proximity_filter(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify proximity filtering with haversine calculation."""
    _, _, headers = donor_user
    # New York coordinates (40.7128, -74.0060)
    await _create_sample_listing(
        client, headers, title="NYC Food", latitude=40.7128, longitude=-74.0060
    )
    # Los Angeles coordinates (34.0522, -118.2437) — approx 3935 km away
    await _create_sample_listing(
        client, headers, title="LA Food", latitude=34.0522, longitude=-118.2437
    )

    # Search within 50 km of NYC
    response = await client.get(
        "/listings/?lat=40.7128&lon=-74.0060&max_distance_km=50"
    )
    assert response.status_code == 200
    items = response.json()["items"]
    titles = [item["title"] for item in items]
    assert "NYC Food" in titles
    assert "LA Food" not in titles


async def test_get_listing_by_id_success(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify public retrieval of single listing with donor details."""
    user, _, headers = donor_user
    created = await _create_sample_listing(client, headers, title="Detailed Listing")

    response = await client.get(f"/listings/{created['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"]
    assert data["title"] == "Detailed Listing"
    assert data["donor"]["name"] == "Alice Donor"
    assert data["donor"]["id"] == user.id


async def test_get_listing_not_found(client: httpx.AsyncClient):
    """Verify 404 on non-existent listing ID."""
    response = await client.get("/listings/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ── 3. Claim Flow & Double-Claim Prevention ───────────────────────────────────
async def test_claim_listing_receiver_success(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
    db_session: AsyncSession,
):
    """
    Verify complete claim flow:
    - Receiver claims listing -> 201 Created
    - Listing status changes from 'available' to 'claimed'
    - Claim record status is 'pending'
    - In-app notification is stored for donor
    """
    donor, _, donor_headers = donor_user
    receiver, _, receiver_headers = receiver_user

    listing = await _create_sample_listing(client, donor_headers, title="Claimable Soup")
    listing_id = listing["id"]

    claim_payload = {"notes": "I can pick up at 2 PM"}
    response = await client.post(
        f"/listings/{listing_id}/claim",
        json=claim_payload,
        headers=receiver_headers,
    )
    assert response.status_code == 201
    claim_data = response.json()
    assert claim_data["listing_id"] == listing_id
    assert claim_data["receiver_id"] == receiver.id
    assert claim_data["status"] == "pending"
    assert claim_data["notes"] == "I can pick up at 2 PM"

    # Verify listing status transitioned to 'claimed'
    get_res = await client.get(f"/listings/{listing_id}")
    assert get_res.json()["status"] == "claimed"

    # Verify in-app Notification row was written to the DB
    notif_res = await db_session.execute(
        select(Notification).where(Notification.user_id == donor.id)
    )
    notifications = notif_res.scalars().all()
    assert len(notifications) >= 1
    assert any("Claimable Soup" in n.message for n in notifications)


async def test_claim_listing_prevent_double_claim(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
    other_receiver_user: tuple[User, str, dict[str, str]],
):
    """Verify that once claimed, subsequent claims return 409 Conflict (no double claiming)."""
    _, _, donor_headers = donor_user
    _, _, receiver1_headers = receiver_user
    _, _, receiver2_headers = other_receiver_user

    listing = await _create_sample_listing(client, donor_headers, title="Single Meal")
    listing_id = listing["id"]

    # First claim succeeds
    res1 = await client.post(
        f"/listings/{listing_id}/claim",
        json={"notes": "First receiver"},
        headers=receiver1_headers,
    )
    assert res1.status_code == 201

    # Second claim MUST fail with 409 Conflict
    res2 = await client.post(
        f"/listings/{listing_id}/claim",
        json={"notes": "Second receiver attempting claim"},
        headers=receiver2_headers,
    )
    assert res2.status_code == 409
    assert "no longer available" in res2.json()["detail"].lower()


async def test_claim_listing_rejected_for_donor(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that a donor cannot claim listings (403 Forbidden)."""
    _, _, donor_headers = donor_user
    listing = await _create_sample_listing(client, donor_headers, title="Self Claim Test")

    response = await client.post(
        f"/listings/{listing['id']}/claim",
        json={"notes": "Donor trying to claim"},
        headers=donor_headers,
    )
    assert response.status_code == 403


# ── 4. Permissions & Edit/Delete Guards ───────────────────────────────────────
async def test_update_listing_owner_donor_success(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that the owning donor can edit an available listing."""
    _, _, headers = donor_user
    listing = await _create_sample_listing(client, headers, title="Original Bread Title")

    update_payload = {"title": "Updated Artisanal Bread", "quantity": 15.0}
    response = await client.put(
        f"/listings/{listing['id']}",
        json=update_payload,
        headers=headers,
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Updated Artisanal Bread"
    assert updated["quantity"] == 15.0


async def test_update_listing_forbidden_for_other_donor(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    other_donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that a donor cannot edit another donor's listing (403 Forbidden)."""
    _, _, donor1_headers = donor_user
    _, _, donor2_headers = other_donor_user

    listing = await _create_sample_listing(client, donor1_headers, title="Donor 1 Food")

    response = await client.put(
        f"/listings/{listing['id']}",
        json={"title": "Hijacked Title"},
        headers=donor2_headers,
    )
    assert response.status_code == 403
    assert "own listings" in response.json()["detail"].lower()


async def test_update_listing_forbidden_when_claimed(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
):
    """Verify that once a listing is claimed, it cannot be modified (400 Bad Request)."""
    _, _, donor_headers = donor_user
    _, _, receiver_headers = receiver_user

    listing = await _create_sample_listing(client, donor_headers, title="Freeze Check")
    listing_id = listing["id"]

    # Claim the listing
    await client.post(
        f"/listings/{listing_id}/claim",
        json={"notes": "Claiming before update"},
        headers=receiver_headers,
    )

    # Attempt update by donor
    response = await client.put(
        f"/listings/{listing_id}",
        json={"title": "Trying to edit claimed item"},
        headers=donor_headers,
    )
    assert response.status_code == 400
    assert "cannot be edited" in response.json()["detail"].lower()


async def test_cancel_listing_soft_delete(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
):
    """Verify soft-delete (DELETE /listings/{id} sets status to 'cancelled')."""
    _, _, headers = donor_user
    listing = await _create_sample_listing(client, headers, title="Cancellable Pastries")
    listing_id = listing["id"]

    delete_res = await client.delete(f"/listings/{listing_id}", headers=headers)
    assert delete_res.status_code == 204

    # Verify status is now 'cancelled'
    get_res = await client.get(f"/listings/{listing_id}")
    assert get_res.json()["status"] == "cancelled"


async def test_cancel_listing_forbidden_for_other_donor(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    other_donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that another donor cannot cancel someone else's listing (403 Forbidden)."""
    _, _, donor1_headers = donor_user
    _, _, donor2_headers = other_donor_user

    listing = await _create_sample_listing(client, donor1_headers, title="Protected Listing")

    response = await client.delete(f"/listings/{listing['id']}", headers=donor2_headers)
    assert response.status_code == 403


# ── 5. Completion Flow (Pickup) ───────────────────────────────────────────────
async def test_complete_listing_by_donor(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
):
    """Verify that donor can mark claimed listing as picked_up / completed."""
    _, _, donor_headers = donor_user
    _, _, receiver_headers = receiver_user

    listing = await _create_sample_listing(client, donor_headers, title="Pickup Item")
    listing_id = listing["id"]

    # Receiver claims it
    await client.post(f"/listings/{listing_id}/claim", json={}, headers=receiver_headers)

    # Donor completes it
    response = await client.post(f"/listings/{listing_id}/complete", headers=donor_headers)
    assert response.status_code == 200
    claim_data = response.json()
    assert claim_data["status"] == "completed"

    # Verify listing status is 'picked_up'
    get_res = await client.get(f"/listings/{listing_id}")
    assert get_res.json()["status"] == "picked_up"


async def test_complete_listing_by_receiver(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
):
    """Verify that claiming receiver can also mark listing as completed."""
    _, _, donor_headers = donor_user
    _, _, receiver_headers = receiver_user

    listing = await _create_sample_listing(client, donor_headers, title="Receiver Pickup Item")
    listing_id = listing["id"]

    # Receiver claims it
    await client.post(f"/listings/{listing_id}/claim", json={}, headers=receiver_headers)

    # Receiver completes it
    response = await client.post(f"/listings/{listing_id}/complete", headers=receiver_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


async def test_complete_listing_unauthorized_user(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
    other_donor_user: tuple[User, str, dict[str, str]],
):
    """Verify that an uninvolved third-party user cannot complete a listing (403 Forbidden)."""
    _, _, donor_headers = donor_user
    _, _, receiver_headers = receiver_user
    _, _, other_donor_headers = other_donor_user

    listing = await _create_sample_listing(client, donor_headers, title="Unauthorized Complete")
    listing_id = listing["id"]

    await client.post(f"/listings/{listing_id}/claim", json={}, headers=receiver_headers)

    # Uninvolved donor attempts complete
    response = await client.post(f"/listings/{listing_id}/complete", headers=other_donor_headers)
    assert response.status_code == 403
    assert "only the listing's donor or the claiming receiver" in response.json()["detail"].lower()
