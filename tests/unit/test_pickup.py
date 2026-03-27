"""Tests for agent/pickup.py — reservation lifecycle."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from agent.pickup import (
    CODE_LENGTH,
    PICKUP_EXPIRY_MINUTES,
    _generate_unique_code,
    _release_stock_for_pickup,
    confirm_pickup,
    create_reservation,
    expire_stale_pickups,
    get_pending_pickups,
)
from db.models import PickupOrder, Product, Transaction

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_broadcast():
    with patch("agent.pickup.broadcast", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_hardware():
    with patch("agent.pickup.get_controller") as m:
        controller = m.return_value
        controller.unlock_door = lambda: None
        yield controller


class TestCreateReservation:
    async def test_valid_single_item(self, seeded_session, mock_broadcast):
        result = await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 2}],
            customer_name="Alice",
            sender_id="U_ALICE",
            platform="slack",
        )
        assert "code" in result
        assert len(result["code"]) == CODE_LENGTH
        assert result["total"] == 3.00  # 2 * $1.50
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Water Bottle"

    async def test_stock_decremented(self, seeded_session, mock_broadcast):
        product = await seeded_session.get(Product, 1)
        initial_qty = product.quantity
        await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 3}],
            customer_name="Bob",
        )
        await seeded_session.refresh(product)
        assert product.quantity == initial_qty - 3

    async def test_sale_transactions_created(self, seeded_session, mock_broadcast):
        result = await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Charlie",
        )
        assert len(result["transaction_ids"]) == 1
        txn = await seeded_session.get(Transaction, result["transaction_ids"][0])
        assert txn.type == "sale"
        assert txn.amount == 1.50

    async def test_30_min_expiry(self, seeded_session, mock_broadcast):
        result = await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Dave",
        )
        pickup = (await seeded_session.execute(
            select(PickupOrder).where(PickupOrder.code == result["code"])
        )).scalar_one()
        assert pickup.expires_at is not None
        # Should be about 30 minutes from now
        delta = pickup.expires_at - datetime.utcnow()
        assert 28 * 60 < delta.total_seconds() < 31 * 60

    async def test_multi_item_reservation(self, seeded_session, mock_broadcast):
        result = await create_reservation(
            seeded_session,
            items=[
                {"product_id": 1, "quantity": 1},
                {"product_id": 2, "quantity": 2},
            ],
            customer_name="Eve",
        )
        assert result["total"] == 1.50 + 4.00  # 1*1.50 + 2*2.00
        assert len(result["items"]) == 2
        assert len(result["transaction_ids"]) == 2

    async def test_broadcasts_stock_updates(self, seeded_session, mock_broadcast):
        await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Frank",
        )
        assert mock_broadcast.called
        call_args = mock_broadcast.call_args_list[-1][0][0]
        assert call_args["type"] == "stock_update"


class TestConfirmPickup:
    async def _create_test_reservation(self, session, mock_broadcast):
        return await create_reservation(
            session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Test",
            sender_id="U_TEST",
        )

    async def test_valid_code(self, seeded_session, mock_broadcast, mock_hardware):
        reservation = await self._create_test_reservation(seeded_session, mock_broadcast)
        result = await confirm_pickup(seeded_session, reservation["code"])
        assert result["success"] is True
        assert result["code"] == reservation["code"]

    async def test_nonexistent_code(self, seeded_session, mock_broadcast, mock_hardware):
        result = await confirm_pickup(seeded_session, "XXXXXX")
        assert result["success"] is False
        assert "not found" in result["error"]

    async def test_already_picked_up(self, seeded_session, mock_broadcast, mock_hardware):
        reservation = await self._create_test_reservation(seeded_session, mock_broadcast)
        await confirm_pickup(seeded_session, reservation["code"])
        result = await confirm_pickup(seeded_session, reservation["code"])
        assert result["success"] is False
        assert "already been picked up" in result["error"]

    async def test_expired_code(self, seeded_session, mock_broadcast, mock_hardware):
        reservation = await self._create_test_reservation(seeded_session, mock_broadcast)
        # Manually expire it
        pickup = (await seeded_session.execute(
            select(PickupOrder).where(PickupOrder.code == reservation["code"])
        )).scalar_one()
        pickup.expires_at = datetime.utcnow() - timedelta(minutes=1)
        await seeded_session.commit()
        result = await confirm_pickup(seeded_session, reservation["code"])
        assert result["success"] is False
        assert "expired" in result["error"]

    async def test_case_insensitive(self, seeded_session, mock_broadcast, mock_hardware):
        reservation = await self._create_test_reservation(seeded_session, mock_broadcast)
        result = await confirm_pickup(seeded_session, reservation["code"].lower())
        assert result["success"] is True


class TestExpireStalePickups:
    async def test_expires_past_expiry(self, seeded_session, mock_broadcast):
        reservation = await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Stale",
        )
        # Set expiry to the past
        pickup = (await seeded_session.execute(
            select(PickupOrder).where(PickupOrder.code == reservation["code"])
        )).scalar_one()
        pickup.expires_at = datetime.utcnow() - timedelta(minutes=5)
        await seeded_session.commit()

        expired = await expire_stale_pickups(seeded_session)
        assert reservation["code"] in expired

    async def test_ignores_already_expired(self, seeded_session, mock_broadcast):
        reservation = await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Already",
        )
        pickup = (await seeded_session.execute(
            select(PickupOrder).where(PickupOrder.code == reservation["code"])
        )).scalar_one()
        pickup.status = "expired"
        pickup.expires_at = datetime.utcnow() - timedelta(minutes=5)
        await seeded_session.commit()

        expired = await expire_stale_pickups(seeded_session)
        assert reservation["code"] not in expired

    async def test_ignores_picked_up(self, seeded_session, mock_broadcast):
        reservation = await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Done",
        )
        pickup = (await seeded_session.execute(
            select(PickupOrder).where(PickupOrder.code == reservation["code"])
        )).scalar_one()
        pickup.status = "picked_up"
        pickup.expires_at = datetime.utcnow() - timedelta(minutes=5)
        await seeded_session.commit()

        expired = await expire_stale_pickups(seeded_session)
        assert reservation["code"] not in expired

    async def test_returns_expired_codes(self, seeded_session, mock_broadcast):
        expired = await expire_stale_pickups(seeded_session)
        assert isinstance(expired, list)


class TestReleaseStockForPickup:
    async def test_restores_quantities(self, seeded_session, mock_broadcast):
        product = await seeded_session.get(Product, 1)
        initial_qty = product.quantity

        reservation = await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 2}],
            customer_name="Refund",
        )
        await seeded_session.refresh(product)
        assert product.quantity == initial_qty - 2

        # Now release
        pickup = (await seeded_session.execute(
            select(PickupOrder).where(PickupOrder.code == reservation["code"])
        )).scalar_one()
        await _release_stock_for_pickup(seeded_session, pickup)
        await seeded_session.refresh(product)
        assert product.quantity == initial_qty

    async def test_creates_refund_transactions(self, seeded_session, mock_broadcast):
        reservation = await create_reservation(
            seeded_session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Refund",
        )
        pickup = (await seeded_session.execute(
            select(PickupOrder).where(PickupOrder.code == reservation["code"])
        )).scalar_one()
        await _release_stock_for_pickup(seeded_session, pickup)

        refunds = (await seeded_session.execute(
            select(Transaction).where(Transaction.type == "refund")
        )).scalars().all()
        assert len(refunds) >= 1
        assert refunds[0].amount < 0  # Negative (refund)


class TestGenerateUniqueCode:
    async def test_6_char_alphanumeric(self, db_session):
        code = await _generate_unique_code(db_session)
        assert len(code) == CODE_LENGTH
        assert code.isalnum()
        assert code.isupper() or code.isdigit() or code.isalpha()

    async def test_unique_codes(self, db_session):
        codes = set()
        for _ in range(20):
            code = await _generate_unique_code(db_session)
            codes.add(code)
        # All should be unique
        assert len(codes) == 20
