"""Tests for db/models.py — ORM model creation and defaults."""

import pytest
from sqlalchemy import select

from db.models import (
    AgentDecision,
    AgentEpisode,
    AgentKnowledge,
    CustomerProfile,
    DailyMetric,
    KVStore,
    Message,
    PickupOrder,
    Product,
    ProductRequest,
    Scratchpad,
    Transaction,
    UserInteraction,
)

pytestmark = pytest.mark.unit


class TestProductModel:
    async def test_create_product(self, db_session):
        p = Product(name="Test", cost_price=1.0, sell_price=2.0, quantity=5)
        db_session.add(p)
        await db_session.commit()
        assert p.id is not None
        assert p.is_active is True  # default

    async def test_default_quantity(self, db_session):
        p = Product(name="Test", cost_price=1.0, sell_price=2.0)
        db_session.add(p)
        await db_session.commit()
        assert p.quantity == 0

    async def test_unique_sku(self, db_session):
        db_session.add(Product(name="A", sku="SKU-1", cost_price=1.0, sell_price=2.0))
        await db_session.commit()
        db_session.add(Product(name="B", sku="SKU-1", cost_price=1.0, sell_price=2.0))
        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()


class TestTransactionModel:
    async def test_create_transaction(self, db_session):
        txn = Transaction(type="sale", amount=5.00, notes="Test sale")
        db_session.add(txn)
        await db_session.commit()
        assert txn.id is not None


class TestAgentDecisionModel:
    async def test_create_decision(self, db_session):
        d = AgentDecision(trigger="test", action="test_action", was_blocked=False)
        db_session.add(d)
        await db_session.commit()
        assert d.id is not None
        assert d.was_blocked is False


class TestScratchpadModel:
    async def test_primary_key_is_key(self, db_session):
        s = Scratchpad(key="note1", value="hello")
        db_session.add(s)
        await db_session.commit()
        found = await db_session.get(Scratchpad, "note1")
        assert found is not None
        assert found.value == "hello"


class TestKVStoreModel:
    async def test_primary_key_is_key(self, db_session):
        kv = KVStore(key="setting1", value="val1")
        db_session.add(kv)
        await db_session.commit()
        found = await db_session.get(KVStore, "setting1")
        assert found.value == "val1"


class TestMessageModel:
    async def test_create_message(self, db_session):
        m = Message(direction="customer_to_agent", content="Hello")
        db_session.add(m)
        await db_session.commit()
        assert m.id is not None


class TestUserInteractionModel:
    async def test_create_interaction(self, db_session):
        ui = UserInteraction(session_id="sess1", sender_id="U1")
        db_session.add(ui)
        await db_session.commit()
        assert ui.id is not None
        assert ui.guardrail_hit is False  # default


class TestProductRequestModel:
    async def test_default_status(self, db_session):
        pr = ProductRequest(query="kombucha", product_name="GT's Kombucha")
        db_session.add(pr)
        await db_session.commit()
        assert pr.status == "pending"


class TestPickupOrderModel:
    async def test_create_pickup(self, db_session):
        po = PickupOrder(
            code="ABC123",
            items_json='[{"name": "Water"}]',
            total_amount=1.50,
        )
        db_session.add(po)
        await db_session.commit()
        assert po.id is not None
        assert po.status == "reserved"  # default


class TestCustomerProfileModel:
    async def test_defaults(self, db_session):
        cp = CustomerProfile(sender_id="U123", display_name="Alice")
        db_session.add(cp)
        await db_session.commit()
        assert cp.total_spend == 0.0
        assert cp.purchase_count == 0


class TestAgentEpisodeModel:
    async def test_create_episode(self, db_session):
        ep = AgentEpisode(event_type="sale", summary="Sold 2 water bottles")
        db_session.add(ep)
        await db_session.commit()
        assert ep.id is not None


class TestAgentKnowledgeModel:
    async def test_create_knowledge(self, db_session):
        k = AgentKnowledge(
            topic="Demand", insight="Energy drinks popular on Mondays", keywords="energy,monday"
        )
        db_session.add(k)
        await db_session.commit()
        assert k.id is not None


class TestDailyMetricModel:
    async def test_unique_date(self, db_session):
        db_session.add(DailyMetric(date="2025-01-01"))
        await db_session.commit()
        db_session.add(DailyMetric(date="2025-01-01"))
        with pytest.raises(Exception):
            await db_session.commit()
