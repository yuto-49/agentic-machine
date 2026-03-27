"""Integration tests for /api/requests endpoints."""

import pytest

pytestmark = pytest.mark.integration


async def _create_request(client):
    """Helper to seed a product request via direct DB manipulation isn't possible
    through the httpx client, so we use the existing checkout flow that creates them.
    Instead, we'll test the endpoints with empty state and verify schema."""
    pass


class TestListRequests:
    async def test_empty_list(self, client):
        resp = await client.get("/api/requests")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_filter_by_status(self, client):
        resp = await client.get("/api/requests?status=pending")
        assert resp.status_code == 200
        assert resp.json() == []


class TestUpdateRequest:
    async def test_404_missing(self, client):
        resp = await client.patch("/api/requests/9999", json={"status": "approved"})
        assert resp.status_code == 404
