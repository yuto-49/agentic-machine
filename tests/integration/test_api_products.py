"""Integration tests for GET /api/products endpoints."""

import pytest

pytestmark = pytest.mark.integration


class TestListProducts:
    async def test_returns_200(self, client):
        resp = await client.get("/api/products")
        assert resp.status_code == 200

    async def test_returns_active_products(self, client):
        resp = await client.get("/api/products")
        data = resp.json()
        assert len(data) == 10
        assert all(p["is_active"] for p in data)

    async def test_product_schema(self, client):
        resp = await client.get("/api/products")
        product = resp.json()[0]
        assert "id" in product
        assert "name" in product
        assert "sell_price" in product
        assert "quantity" in product
        assert "slot" in product


class TestGetProduct:
    async def test_existing_product(self, client):
        resp = await client.get("/api/products/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Water Bottle"
        assert data["sell_price"] == 1.50

    async def test_404_for_missing(self, client):
        resp = await client.get("/api/products/9999")
        assert resp.status_code == 404
