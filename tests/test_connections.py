"""
tests/test_connections.py — Donor-Receiver Connections Tests
==============================================================

Tests for connection requests, status checks, acceptance, decline,
and connection guard enforcement during food claiming.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


from tests.test_listings import _create_sample_listing


@pytest.mark.asyncio
async def test_connection_workflow_success(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
):
    """
    Test end-to-end connection request & accept workflow:
    1. Receiver requests connection with Donor -> 201 Created (status = 'pending')
    2. Check status -> status = 'pending_sent' for Receiver, 'pending_received' for Donor
    3. Donor accepts request -> 200 OK (status = 'accepted')
    """
    donor, _, donor_headers = donor_user
    receiver, _, receiver_headers = receiver_user

    # 1. Receiver sends request to Donor
    req_res = await client.post(
        "/connections/request",
        json={"peer_id": donor.id},
        headers=receiver_headers,
    )
    assert req_res.status_code == 201
    conn_data = req_res.json()
    conn_id = conn_data["id"]
    assert conn_data["status"] == "pending"
    assert conn_data["requester_id"] == receiver.id
    assert conn_data["addressee_id"] == donor.id

    # 2. Check status from Receiver perspective
    status_res = await client.get(
        f"/connections/status/{donor.id}",
        headers=receiver_headers,
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "pending_sent"

    # Check status from Donor perspective
    status_res_donor = await client.get(
        f"/connections/status/{receiver.id}",
        headers=donor_headers,
    )
    assert status_res_donor.status_code == 200
    assert status_res_donor.json()["status"] == "pending_received"

    # 3. Donor accepts request
    accept_res = await client.post(
        f"/connections/{conn_id}/accept",
        headers=donor_headers,
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] == "accepted"

    # Verify status is accepted for both
    status_res_final = await client.get(
        f"/connections/status/{donor.id}",
        headers=receiver_headers,
    )
    assert status_res_final.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_claim_food_without_connection_returns_403(
    client: httpx.AsyncClient,
    donor_user: tuple[User, str, dict[str, str]],
    receiver_user: tuple[User, str, dict[str, str]],
):
    """Verify that a receiver cannot claim food unless connected with the donor."""
    _, _, donor_headers = donor_user
    _, _, receiver_headers = receiver_user

    # Donor creates food listing
    listing = await _create_sample_listing(client, donor_headers, title="Unconnected Soup")
    listing_id = listing["id"]

    # Receiver attempts claim without connection -> 403 Forbidden
    claim_res = await client.post(
        f"/listings/{listing_id}/claim",
        json={"notes": "Can I have this?"},
        headers=receiver_headers,
    )
    assert claim_res.status_code == 403
    assert "must be connected with this donor" in claim_res.json()["detail"].lower()

