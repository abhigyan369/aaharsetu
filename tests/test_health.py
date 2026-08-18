"""
tests/test_health.py — Health Check Unit Tests
===============================================
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_200_ok(client: AsyncClient):
    """
    Test that GET /health returns HTTP 200 OK with 'ok' status and 'connected' database.
    """
    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "app" in data
    assert "environment" in data
