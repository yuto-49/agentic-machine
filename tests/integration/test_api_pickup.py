"""Integration tests for pickup endpoints."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PickupOrder

pytestmark = pytest.mark.integration


async def _create_reservation_in_db(client, code="TSTPCK"):
    """Helper: insert a reservation directly via the test app's DB."""
    # We'll use the admin pickups endpoint to verify, but create via a more direct path
    # Instead, let's use the test_app's session factory
    pass


class TestPickupConfirm:
    async def test_reject_short_code(self, client):
        resp = await client.post("/api/pickup/confirm", json={"code": "ABC"})
        assert resp.status_code == 400
        assert "exactly 6" in resp.json()["detail"]

    async def test_nonexistent_code(self, client):
        resp = await client.post("/api/pickup/confirm", json={"code": "XXXXXX"})
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"]


class TestPickupStatus:
    async def test_nonexistent_code_404(self, client):
        resp = await client.get("/api/pickup/status/XXXXXX")
        assert resp.status_code == 404


class TestAdminPickups:
    async def test_list_empty(self, client):
        resp = await client.get("/api/admin/pickups")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pickups"] == []

    async def test_force_expire_empty(self, client):
        resp = await client.post("/api/admin/pickups/expire")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["expired_codes"] == []
