"""Tests for agent/guardrails.py — validate_action() business rules."""

import pytest
from agent.guardrails import (
    MAX_CUSTOMER_NOTES_LENGTH,
    MAX_KNOWLEDGE_INSIGHT_LENGTH,
    MAX_ONLINE_ORDER_PRICE,
    MAX_RESTOCK_QTY_PER_ITEM,
    MAX_SINGLE_PURCHASE,
    MIN_MARGIN_MULTIPLIER,
    MAX_PRICE_MULTIPLIER,
    validate_action,
)
from db.models import Product

pytestmark = pytest.mark.unit


# --- set_price ---


class TestSetPriceGuardrails:
    async def test_valid_price(self, seeded_session):
        result = await validate_action(
            "set_price", {"product_id": 1, "new_price": 2.00}, seeded_session
        )
        assert result["allowed"] is True

    async def test_below_min_margin(self, seeded_session):
        # Product 1 cost_price=0.50, min = 0.50*1.3 = 0.65
        result = await validate_action(
            "set_price", {"product_id": 1, "new_price": 0.60}, seeded_session
        )
        assert result["allowed"] is False
        assert "below minimum" in result["reason"]

    async def test_exact_min_margin_boundary(self, seeded_session):
        # Exactly at min: 0.50 * 1.3 = 0.65
        result = await validate_action(
            "set_price", {"product_id": 1, "new_price": 0.65}, seeded_session
        )
        assert result["allowed"] is True

    async def test_above_max_price(self, seeded_session):
        # Product 1 cost=0.50, max = 0.50*5.0 = 2.50
        result = await validate_action(
            "set_price", {"product_id": 1, "new_price": 3.00}, seeded_session
        )
        assert result["allowed"] is False
        assert "exceeds" in result["reason"]

    async def test_exact_max_price_boundary(self, seeded_session):
        # Exactly at max: 0.50 * 5.0 = 2.50
        result = await validate_action(
            "set_price", {"product_id": 1, "new_price": 2.50}, seeded_session
        )
        assert result["allowed"] is True

    async def test_nonexistent_product(self, seeded_session):
        result = await validate_action(
            "set_price", {"product_id": 9999, "new_price": 5.00}, seeded_session
        )
        assert result["allowed"] is False
        assert "not found" in result["reason"]


# --- process_order ---


class TestProcessOrderGuardrails:
    async def test_valid_order(self, seeded_session):
        result = await validate_action(
            "process_order",
            {"items": [{"product_id": 1, "quantity": 2}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is True

    async def test_empty_items(self, seeded_session):
        result = await validate_action(
            "process_order",
            {"items": [], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "at least one item" in result["reason"]

    async def test_zero_quantity(self, seeded_session):
        result = await validate_action(
            "process_order",
            {"items": [{"product_id": 1, "quantity": 0}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "positive" in result["reason"]

    async def test_negative_quantity(self, seeded_session):
        result = await validate_action(
            "process_order",
            {"items": [{"product_id": 1, "quantity": -1}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False

    async def test_inactive_product(self, seeded_session):
        product = await seeded_session.get(Product, 1)
        product.is_active = False
        await seeded_session.commit()
        result = await validate_action(
            "process_order",
            {"items": [{"product_id": 1, "quantity": 1}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "not currently available" in result["reason"]

    async def test_insufficient_stock(self, seeded_session):
        result = await validate_action(
            "process_order",
            {"items": [{"product_id": 1, "quantity": 999}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "Insufficient stock" in result["reason"]

    async def test_over_80_limit(self, seeded_session):
        # Energy Drink is $3.50, 24 units = $84 > $80
        product = await seeded_session.get(Product, 4)
        product.quantity = 30
        await seeded_session.commit()
        result = await validate_action(
            "process_order",
            {"items": [{"product_id": 4, "quantity": 24}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "exceeds maximum" in result["reason"]

    async def test_exact_80_boundary(self, seeded_session):
        # Product 2 (Coca-Cola) $2.00 * 40 = $80.00 exactly
        product = await seeded_session.get(Product, 2)
        product.quantity = 50
        await seeded_session.commit()
        result = await validate_action(
            "process_order",
            {"items": [{"product_id": 2, "quantity": 40}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is True

    async def test_nonexistent_product(self, seeded_session):
        result = await validate_action(
            "process_order",
            {"items": [{"product_id": 9999, "quantity": 1}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "not found" in result["reason"]


# --- create_pickup_reservation ---


class TestCreatePickupReservationGuardrails:
    async def test_valid_reservation(self, seeded_session):
        result = await validate_action(
            "create_pickup_reservation",
            {"items": [{"product_id": 1, "quantity": 1}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is True

    async def test_empty_items(self, seeded_session):
        result = await validate_action(
            "create_pickup_reservation",
            {"items": [], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False

    async def test_over_80_limit(self, seeded_session):
        product = await seeded_session.get(Product, 4)
        product.quantity = 30
        await seeded_session.commit()
        result = await validate_action(
            "create_pickup_reservation",
            {"items": [{"product_id": 4, "quantity": 24}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "exceeds maximum" in result["reason"]

    async def test_insufficient_stock(self, seeded_session):
        result = await validate_action(
            "create_pickup_reservation",
            {"items": [{"product_id": 1, "quantity": 999}], "customer_name": "Test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "Insufficient stock" in result["reason"]


# --- confirm_pickup ---


class TestConfirmPickupGuardrails:
    async def test_valid_6char_code(self, seeded_session):
        result = await validate_action(
            "confirm_pickup", {"code": "ABC123"}, seeded_session
        )
        assert result["allowed"] is True

    async def test_short_code(self, seeded_session):
        result = await validate_action(
            "confirm_pickup", {"code": "ABC"}, seeded_session
        )
        assert result["allowed"] is False
        assert "exactly 6" in result["reason"]

    async def test_long_code(self, seeded_session):
        result = await validate_action(
            "confirm_pickup", {"code": "ABCDEFGH"}, seeded_session
        )
        assert result["allowed"] is False

    async def test_empty_code(self, seeded_session):
        result = await validate_action(
            "confirm_pickup", {"code": ""}, seeded_session
        )
        assert result["allowed"] is False


# --- unlock_door ---


class TestUnlockDoorGuardrails:
    async def test_with_reason(self, seeded_session):
        result = await validate_action(
            "unlock_door", {"reason": "Restocking drinks"}, seeded_session
        )
        assert result["allowed"] is True

    async def test_empty_reason(self, seeded_session):
        result = await validate_action(
            "unlock_door", {"reason": ""}, seeded_session
        )
        assert result["allowed"] is False
        assert "reason" in result["reason"].lower()

    async def test_whitespace_only_reason(self, seeded_session):
        result = await validate_action(
            "unlock_door", {"reason": "   "}, seeded_session
        )
        assert result["allowed"] is False


# --- request_restock ---


class TestRestockGuardrails:
    async def test_valid_qty(self, seeded_session):
        result = await validate_action(
            "request_restock",
            {"items": [{"product_id": 1, "quantity": 10}], "urgency": "medium"},
            seeded_session,
        )
        assert result["allowed"] is True

    async def test_over_50(self, seeded_session):
        result = await validate_action(
            "request_restock",
            {"items": [{"product_id": 1, "quantity": 51}], "urgency": "medium"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "exceeds max" in result["reason"]

    async def test_zero_qty(self, seeded_session):
        result = await validate_action(
            "request_restock",
            {"items": [{"product_id": 1, "quantity": 0}], "urgency": "medium"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "positive" in result["reason"]

    async def test_negative_qty(self, seeded_session):
        result = await validate_action(
            "request_restock",
            {"items": [{"product_id": 1, "quantity": -5}], "urgency": "medium"},
            seeded_session,
        )
        assert result["allowed"] is False


# --- update_customer_notes ---


class TestUpdateCustomerNotesGuardrails:
    async def test_within_limit(self, seeded_session):
        result = await validate_action(
            "update_customer_notes",
            {"sender_id": "U123", "notes": "Likes cold drinks"},
            seeded_session,
        )
        assert result["allowed"] is True

    async def test_over_500_chars(self, seeded_session):
        result = await validate_action(
            "update_customer_notes",
            {"sender_id": "U123", "notes": "x" * 501},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "500" in result["reason"]

    async def test_exact_500_boundary(self, seeded_session):
        result = await validate_action(
            "update_customer_notes",
            {"sender_id": "U123", "notes": "x" * 500},
            seeded_session,
        )
        assert result["allowed"] is True


# --- record_knowledge ---


class TestRecordKnowledgeGuardrails:
    async def test_valid(self, seeded_session):
        result = await validate_action(
            "record_knowledge",
            {"topic": "Demand", "insight": "Energy drinks sell well on Mondays", "keywords": "energy,monday"},
            seeded_session,
        )
        assert result["allowed"] is True

    async def test_empty_topic(self, seeded_session):
        result = await validate_action(
            "record_knowledge",
            {"topic": "", "insight": "Some insight", "keywords": "test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "Topic" in result["reason"]

    async def test_empty_keywords(self, seeded_session):
        result = await validate_action(
            "record_knowledge",
            {"topic": "Demand", "insight": "Some insight", "keywords": ""},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "Keywords" in result["reason"]

    async def test_insight_over_1000(self, seeded_session):
        result = await validate_action(
            "record_knowledge",
            {"topic": "Demand", "insight": "x" * 1001, "keywords": "test"},
            seeded_session,
        )
        assert result["allowed"] is False
        assert "1000" in result["reason"]


# --- request_online_product ---


class TestRequestOnlineProductGuardrails:
    async def test_valid(self, seeded_session):
        result = await validate_action(
            "request_online_product",
            {
                "query": "kombucha",
                "product_name": "GT's Kombucha",
                "estimated_price": 4.99,
                "source_url": "https://example.com/kombucha",
            },
            seeded_session,
        )
        assert result["allowed"] is True

    async def test_zero_price(self, seeded_session):
        result = await validate_action(
            "request_online_product",
            {
                "query": "test",
                "product_name": "Test",
                "estimated_price": 0,
                "source_url": "https://example.com",
            },
            seeded_session,
        )
        assert result["allowed"] is False
        assert "positive" in result["reason"]

    async def test_negative_price(self, seeded_session):
        result = await validate_action(
            "request_online_product",
            {
                "query": "test",
                "product_name": "Test",
                "estimated_price": -5,
                "source_url": "https://example.com",
            },
            seeded_session,
        )
        assert result["allowed"] is False

    async def test_over_150(self, seeded_session):
        result = await validate_action(
            "request_online_product",
            {
                "query": "test",
                "product_name": "Expensive Item",
                "estimated_price": 200,
                "source_url": "https://example.com",
            },
            seeded_session,
        )
        assert result["allowed"] is False
        assert "150" in result["reason"]

    async def test_empty_product_name(self, seeded_session):
        result = await validate_action(
            "request_online_product",
            {
                "query": "test",
                "product_name": "",
                "estimated_price": 5,
                "source_url": "https://example.com",
            },
            seeded_session,
        )
        assert result["allowed"] is False
        assert "Product name" in result["reason"]

    async def test_empty_source_url(self, seeded_session):
        result = await validate_action(
            "request_online_product",
            {
                "query": "test",
                "product_name": "Test",
                "estimated_price": 5,
                "source_url": "",
            },
            seeded_session,
        )
        assert result["allowed"] is False
        assert "Source URL" in result["reason"]


# --- Unknown tools pass through ---


class TestPassthroughTools:
    async def test_unknown_tool_allowed(self, seeded_session):
        result = await validate_action("get_inventory", {}, seeded_session)
        assert result["allowed"] is True

    async def test_get_balance_allowed(self, seeded_session):
        result = await validate_action("get_balance", {}, seeded_session)
        assert result["allowed"] is True
