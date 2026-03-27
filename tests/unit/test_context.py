"""Tests for agent/context.py — 5-channel selective recall."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from agent.context import (
    _recall_business_context,
    _recall_customer,
    _recall_episodes,
    _recall_knowledge,
    _recall_pending_pickups,
    log_episode,
    prime_context,
)
from db.models import (
    AgentEpisode,
    AgentKnowledge,
    CustomerProfile,
    PickupOrder,
    Product,
    Transaction,
)

pytestmark = pytest.mark.unit


class TestPrimeContext:
    async def test_empty_data_returns_empty(self, db_session):
        result = await prime_context(None, None, "hello", db_session)
        # With no data, some channels return empty strings, context may be empty
        # Business context always returns balance, so this should have content
        assert isinstance(result, str)

    async def test_context_tags(self, seeded_session):
        result = await prime_context("U123", "Alice", "hello", seeded_session)
        if result:
            assert "<context>" in result
            assert "</context>" in result

    async def test_includes_business_context(self, seeded_session):
        result = await prime_context(None, None, "hello", seeded_session)
        assert "Cash balance" in result

    async def test_channel_failure_handled(self, seeded_session):
        # Even if one channel fails, others should work
        with patch("agent.context._recall_episodes", side_effect=Exception("boom")):
            result = await prime_context("U1", "Bob", "hi", seeded_session)
            # Should not raise, just skip the failed channel
            assert isinstance(result, str)


class TestRecallCustomer:
    async def test_new_customer_creates_stub(self, db_session):
        result = await _recall_customer(db_session, "U_NEW", "NewUser")
        assert "New customer" in result
        # Verify profile was created
        profile = (await db_session.execute(
            select(CustomerProfile).where(CustomerProfile.sender_id == "U_NEW")
        )).scalar_one()
        assert profile.display_name == "NewUser"

    async def test_existing_customer(self, db_session):
        db_session.add(CustomerProfile(
            sender_id="U_EXIST",
            display_name="Alice",
            total_spend=50.0,
            purchase_count=5,
        ))
        await db_session.commit()
        result = await _recall_customer(db_session, "U_EXIST", "Alice")
        assert "Alice" in result
        assert "$50.00" in result
        assert "5 purchases" in result

    async def test_updates_last_seen(self, db_session):
        db_session.add(CustomerProfile(
            sender_id="U_SEEN",
            display_name="Bob",
        ))
        await db_session.commit()
        before = datetime.utcnow()
        await _recall_customer(db_session, "U_SEEN", "Bob")
        profile = (await db_session.execute(
            select(CustomerProfile).where(CustomerProfile.sender_id == "U_SEEN")
        )).scalar_one()
        assert profile.last_seen >= before

    async def test_no_sender_id_returns_empty(self, db_session):
        result = await _recall_customer(db_session, None, None)
        assert result == ""

    async def test_includes_private_notes(self, db_session):
        db_session.add(CustomerProfile(
            sender_id="U_NOTES",
            display_name="Charlie",
            private_notes="Prefers cold drinks",
        ))
        await db_session.commit()
        result = await _recall_customer(db_session, "U_NOTES", "Charlie")
        assert "Prefers cold drinks" in result


class TestRecallEpisodes:
    async def test_recent_episodes(self, db_session):
        db_session.add(AgentEpisode(
            event_type="sale",
            summary="Sold 2 water bottles",
            timestamp=datetime.utcnow() - timedelta(hours=1),
        ))
        await db_session.commit()
        result = await _recall_episodes(db_session)
        assert "sale" in result
        assert "water bottles" in result

    async def test_old_episodes_excluded(self, db_session):
        db_session.add(AgentEpisode(
            event_type="sale",
            summary="Old sale from yesterday",
            timestamp=datetime.utcnow() - timedelta(hours=10),
        ))
        await db_session.commit()
        result = await _recall_episodes(db_session)
        assert "Old sale" not in result

    async def test_empty_returns_empty_string(self, db_session):
        result = await _recall_episodes(db_session)
        assert result == ""

    async def test_15_item_limit(self, db_session):
        for i in range(20):
            db_session.add(AgentEpisode(
                event_type="sale",
                summary=f"Sale {i}",
                timestamp=datetime.utcnow() - timedelta(minutes=i),
            ))
        await db_session.commit()
        result = await _recall_episodes(db_session)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) <= 15


class TestRecallKnowledge:
    async def test_keyword_matching(self, db_session):
        db_session.add(AgentKnowledge(
            topic="Demand",
            insight="Energy drinks sell well on Mondays",
            keywords="energy,monday,demand",
        ))
        await db_session.commit()
        result = await _recall_knowledge(db_session, "Do you sell energy drinks?")
        assert "Energy drinks" in result

    async def test_short_words_filtered(self, db_session):
        db_session.add(AgentKnowledge(
            topic="Test",
            insight="Short word test",
            keywords="an,is",
        ))
        await db_session.commit()
        result = await _recall_knowledge(db_session, "an is")
        # "an" and "is" are < 3 chars, should be filtered
        assert result == ""

    async def test_5_result_limit(self, db_session):
        for i in range(10):
            db_session.add(AgentKnowledge(
                topic=f"Topic {i}",
                insight=f"Insight {i}",
                keywords="test,water",
            ))
        await db_session.commit()
        result = await _recall_knowledge(db_session, "I need some water for my test")
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) <= 5

    async def test_no_match_returns_empty(self, db_session):
        db_session.add(AgentKnowledge(
            topic="Demand",
            insight="Chips popular",
            keywords="chips,snack",
        ))
        await db_session.commit()
        result = await _recall_knowledge(db_session, "Tell me about quantum physics")
        assert result == ""


class TestRecallPendingPickups:
    async def test_sender_filter(self, db_session):
        db_session.add(PickupOrder(
            code="AAAAAA", status="reserved", items_json="[]",
            total_amount=5.0, sender_id="U1",
            customer_name="Alice",
            expires_at=datetime.utcnow() + timedelta(minutes=20),
        ))
        db_session.add(PickupOrder(
            code="BBBBBB", status="reserved", items_json="[]",
            total_amount=3.0, sender_id="U2",
            customer_name="Bob",
            expires_at=datetime.utcnow() + timedelta(minutes=20),
        ))
        await db_session.commit()
        result = await _recall_pending_pickups(db_session, "U1")
        assert "AAAAAA" in result
        assert "BBBBBB" not in result

    async def test_all_pickups_no_filter(self, db_session):
        db_session.add(PickupOrder(
            code="CCCCCC", status="reserved", items_json="[]",
            total_amount=5.0, sender_id="U1",
            customer_name="Alice",
            expires_at=datetime.utcnow() + timedelta(minutes=20),
        ))
        await db_session.commit()
        result = await _recall_pending_pickups(db_session, None)
        assert "CCCCCC" in result

    async def test_empty_returns_empty(self, db_session):
        result = await _recall_pending_pickups(db_session, "U_NOBODY")
        assert result == ""


class TestRecallBusinessContext:
    async def test_shows_balance(self, seeded_session):
        result = await _recall_business_context(seeded_session)
        assert "Cash balance: $100.00" in result

    async def test_shows_today_revenue(self, seeded_session):
        result = await _recall_business_context(seeded_session)
        assert "Today's revenue" in result

    async def test_low_stock_alerts(self, seeded_session):
        # Product 9 (Instant Ramen) has quantity=4, near low stock threshold
        product = await seeded_session.get(Product, 9)
        product.quantity = 2
        await seeded_session.commit()
        result = await _recall_business_context(seeded_session)
        assert "Low stock" in result
        assert "Instant Ramen" in result


class TestLogEpisode:
    async def test_creates_row(self, db_session):
        await log_episode(
            db_session,
            event_type="sale",
            summary="Sold water",
            sender_id="U1",
            details={"product": "Water", "qty": 1},
        )
        episodes = (await db_session.execute(select(AgentEpisode))).scalars().all()
        assert len(episodes) == 1
        assert episodes[0].event_type == "sale"
        assert episodes[0].summary == "Sold water"
        assert json.loads(episodes[0].details_json)["product"] == "Water"

    async def test_without_details(self, db_session):
        await log_episode(db_session, event_type="alert", summary="Low stock")
        episodes = (await db_session.execute(select(AgentEpisode))).scalars().all()
        assert episodes[0].details_json is None
