"""Integration tests for /api/admin/* endpoints."""

import pytest
from sqlalchemy import select

from db.models import AgentDecision, UserInteraction

pytestmark = pytest.mark.integration


class TestAdminLogs:
    async def test_empty_logs(self, client):
        resp = await client.get("/api/admin/logs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_with_limit(self, client):
        resp = await client.get("/api/admin/logs?limit=10")
        assert resp.status_code == 200

    async def test_logs_after_checkout(self, client):
        # Create a checkout to generate a log entry
        await client.post("/api/cart/checkout", json={
            "items": [{"product_id": 1, "quantity": 1}],
        })
        resp = await client.get("/api/admin/logs")
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["was_blocked"] is False


class TestAdminAnalytics:
    async def test_initial_analytics(self, client):
        resp = await client.get("/api/admin/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_revenue" in data
        assert "total_items_sold" in data
        assert "active_products" in data
        assert data["active_products"] == 10

    async def test_analytics_after_sale(self, client):
        await client.post("/api/cart/checkout", json={
            "items": [{"product_id": 1, "quantity": 2}],
        })
        resp = await client.get("/api/admin/analytics")
        data = resp.json()
        assert data["total_revenue"] == 3.00
        assert data["total_items_sold"] == 2


class TestAdminInteractions:
    async def test_empty_interactions(self, client):
        resp = await client.get("/api/admin/interactions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_with_type_filter(self, client):
        resp = await client.get("/api/admin/interactions?interaction_type=purchase")
        assert resp.status_code == 200


class TestAdminMetrics:
    async def test_empty_metrics(self, client):
        resp = await client.get("/api/admin/metrics")
        assert resp.status_code == 200


class TestAdminRestock:
    async def test_restock(self, client):
        resp = await client.post("/api/admin/restock", json={
            "items": [{"product_id": 1, "quantity": 5}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["restocked"]) == 1
        assert data["restocked"][0]["product"] == "Water Bottle"
        # 10 + 5 = 15, but max_quantity is 15, so capped at 15
        assert data["restocked"][0]["new_quantity"] == 15

    async def test_restock_caps_at_max(self, client):
        resp = await client.post("/api/admin/restock", json={
            "items": [{"product_id": 1, "quantity": 100}],
        })
        data = resp.json()
        assert data["restocked"][0]["new_quantity"] == 15  # max_quantity

    async def test_restock_nonexistent_product(self, client):
        resp = await client.post("/api/admin/restock", json={
            "items": [{"product_id": 9999, "quantity": 5}],
        })
        assert resp.status_code == 200
        assert resp.json()["restocked"] == []
