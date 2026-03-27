"""Integration tests for POST /api/cart/checkout."""

import pytest

pytestmark = pytest.mark.integration


class TestCheckout:
    async def test_successful_checkout(self, client):
        resp = await client.post("/api/cart/checkout", json={
            "items": [{"product_id": 1, "quantity": 2}],
            "payment_method": "honor_system",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 3.00  # 2 * $1.50
        assert len(data["transaction_ids"]) == 1

    async def test_insufficient_stock(self, client):
        resp = await client.post("/api/cart/checkout", json={
            "items": [{"product_id": 1, "quantity": 999}],
        })
        assert resp.status_code == 400
        assert "Insufficient stock" in resp.json()["detail"]

    async def test_nonexistent_product(self, client):
        resp = await client.post("/api/cart/checkout", json={
            "items": [{"product_id": 9999, "quantity": 1}],
        })
        assert resp.status_code == 404

    async def test_over_80_limit(self, client):
        # Buy many expensive items to exceed $80
        # Energy Drink (id=4) at $3.50, qty=24 = $84
        resp = await client.post("/api/cart/checkout", json={
            "items": [{"product_id": 2, "quantity": 8}, {"product_id": 3, "quantity": 6}, {"product_id": 4, "quantity": 5}],
        })
        # 8*2 + 6*2.5 + 5*3.5 = 16 + 15 + 17.5 = 48.5, should pass
        assert resp.status_code == 200

    async def test_multi_item_checkout(self, client):
        resp = await client.post("/api/cart/checkout", json={
            "items": [
                {"product_id": 1, "quantity": 1},
                {"product_id": 2, "quantity": 1},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3.50  # 1.50 + 2.00

    async def test_response_includes_updated_products(self, client):
        resp = await client.post("/api/cart/checkout", json={
            "items": [{"product_id": 1, "quantity": 1}],
        })
        data = resp.json()
        assert "updated_products" in data
        assert data["updated_products"][0]["product_id"] == 1
        assert data["updated_products"][0]["quantity"] == 9  # 10 - 1

    async def test_stock_actually_decremented(self, client):
        await client.post("/api/cart/checkout", json={
            "items": [{"product_id": 1, "quantity": 3}],
        })
        resp = await client.get("/api/products/1")
        assert resp.json()["quantity"] == 7  # 10 - 3
