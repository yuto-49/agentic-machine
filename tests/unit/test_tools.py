"""Tests for agent/tools.py — all tool implementations + execute_tool router."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from agent.memory import AgentMemory
from agent.tools import (
    execute_tool,
    tool_get_balance,
    tool_get_inventory,
    tool_get_sales_report,
    tool_process_order,
    tool_record_knowledge,
    tool_recall_customer,
    tool_request_online_product,
    tool_set_price,
    tool_unlock_door,
    tool_update_customer_notes,
)
from db.models import AgentKnowledge, CustomerProfile, Product, ProductRequest, Transaction

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_broadcast():
    with patch("agent.tools.broadcast", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_hardware():
    with patch("agent.tools._hw", None):
        with patch("agent.tools.get_controller") as m:
            controller = m.return_value
            controller.unlock_door = lambda: None
            yield controller


class TestToolGetInventory:
    async def test_returns_json_list(self, seeded_session):
        result = await tool_get_inventory(seeded_session)
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 10

    async def test_only_active_products(self, seeded_session):
        product = await seeded_session.get(Product, 1)
        product.is_active = False
        await seeded_session.commit()
        result = await tool_get_inventory(seeded_session)
        data = json.loads(result)
        assert len(data) == 9
        assert all(p["id"] != 1 for p in data)

    async def test_product_fields(self, seeded_session):
        result = await tool_get_inventory(seeded_session)
        data = json.loads(result)
        item = data[0]
        assert "id" in item
        assert "name" in item
        assert "sell_price" in item
        assert "quantity" in item


class TestToolSetPrice:
    async def test_updates_price(self, seeded_session):
        result = await tool_set_price(seeded_session, 1, 2.00)
        assert "Price updated" in result
        product = await seeded_session.get(Product, 1)
        assert product.sell_price == 2.00

    async def test_nonexistent_product(self, seeded_session):
        result = await tool_set_price(seeded_session, 9999, 5.00)
        assert "not found" in result


class TestToolGetBalance:
    async def test_returns_balance_and_transactions(self, seeded_session):
        result = await tool_get_balance(seeded_session)
        data = json.loads(result)
        assert "balance" in data
        assert data["balance"] == 100.00
        assert "recent_transactions" in data


class TestToolUnlockDoor:
    async def test_returns_reason(self, mock_hardware):
        # Reset the lazy-init
        import agent.tools
        agent.tools._hw = mock_hardware
        result = await tool_unlock_door("Restocking")
        assert "Restocking" in result


class TestToolGetSalesReport:
    async def test_returns_summary(self, seeded_session):
        result = await tool_get_sales_report(seeded_session, 7)
        data = json.loads(result)
        assert "period_days" in data
        assert data["period_days"] == 7
        assert "total_revenue" in data


class TestToolProcessOrder:
    async def test_successful_order(self, seeded_session, mock_broadcast):
        result = await tool_process_order(
            seeded_session,
            items=[{"product_id": 1, "quantity": 2}],
            customer_name="Alice",
        )
        data = json.loads(result)
        assert data["success"] is True
        assert data["total"] == 3.00

    async def test_stock_decremented(self, seeded_session, mock_broadcast):
        product = await seeded_session.get(Product, 1)
        initial = product.quantity
        await tool_process_order(
            seeded_session,
            items=[{"product_id": 1, "quantity": 3}],
            customer_name="Bob",
        )
        await seeded_session.refresh(product)
        assert product.quantity == initial - 3

    async def test_transactions_created(self, seeded_session, mock_broadcast):
        result = await tool_process_order(
            seeded_session,
            items=[{"product_id": 1, "quantity": 1}],
            customer_name="Charlie",
        )
        data = json.loads(result)
        assert len(data["transaction_ids"]) == 1


class TestToolRecallCustomer:
    async def test_not_found(self, seeded_session):
        result = await tool_recall_customer(seeded_session, "U_NONEXIST")
        data = json.loads(result)
        assert data["found"] is False

    async def test_found(self, seeded_session):
        seeded_session.add(CustomerProfile(
            sender_id="U_ALICE", display_name="Alice", total_spend=25.0, purchase_count=3,
        ))
        await seeded_session.commit()
        result = await tool_recall_customer(seeded_session, "U_ALICE")
        data = json.loads(result)
        assert data["found"] is True
        assert data["display_name"] == "Alice"
        assert data["total_spend"] == 25.0


class TestToolUpdateCustomerNotes:
    async def test_creates_profile_if_missing(self, seeded_session):
        result = await tool_update_customer_notes(seeded_session, "U_NEW", "Likes cola")
        assert "Notes updated" in result
        profile = (await seeded_session.execute(
            select(CustomerProfile).where(CustomerProfile.sender_id == "U_NEW")
        )).scalar_one()
        assert profile.private_notes == "Likes cola"

    async def test_updates_existing_notes(self, seeded_session):
        seeded_session.add(CustomerProfile(
            sender_id="U_EXIST", display_name="Bob", private_notes="Old notes",
        ))
        await seeded_session.commit()
        await tool_update_customer_notes(seeded_session, "U_EXIST", "New notes")
        profile = (await seeded_session.execute(
            select(CustomerProfile).where(CustomerProfile.sender_id == "U_EXIST")
        )).scalar_one()
        assert profile.private_notes == "New notes"


class TestToolRecordKnowledge:
    async def test_creates_entry(self, seeded_session):
        result = await tool_record_knowledge(
            seeded_session, "Demand", "Water popular at noon", "water,noon",
        )
        data = json.loads(result)
        assert data["topic"] == "Demand"
        assert data["id"] is not None


class TestToolRequestOnlineProduct:
    async def test_creates_request(self, seeded_session, mock_broadcast):
        result = await tool_request_online_product(
            seeded_session,
            query="kombucha",
            product_name="GT's Kombucha",
            estimated_price=4.99,
            source_url="https://example.com/kombucha",
        )
        data = json.loads(result)
        assert data["success"] is True
        assert data["request_id"] is not None
        req = await seeded_session.get(ProductRequest, data["request_id"])
        assert req.status == "pending"


class TestExecuteToolRouter:
    async def test_get_inventory(self, seeded_session):
        mem = AgentMemory(seeded_session)
        result = await execute_tool("get_inventory", {}, seeded_session, mem)
        data = json.loads(result)
        assert isinstance(data, list)

    async def test_get_balance(self, seeded_session):
        mem = AgentMemory(seeded_session)
        result = await execute_tool("get_balance", {}, seeded_session, mem)
        data = json.loads(result)
        assert "balance" in data

    async def test_write_scratchpad(self, seeded_session):
        mem = AgentMemory(seeded_session)
        result = await execute_tool(
            "write_scratchpad", {"key": "test", "value": "hello"}, seeded_session, mem
        )
        assert "Saved" in result

    async def test_read_scratchpad(self, seeded_session):
        mem = AgentMemory(seeded_session)
        await execute_tool("write_scratchpad", {"key": "k", "value": "v"}, seeded_session, mem)
        result = await execute_tool("read_scratchpad", {"key": "k"}, seeded_session, mem)
        assert result == "v"

    async def test_unknown_tool(self, seeded_session):
        mem = AgentMemory(seeded_session)
        result = await execute_tool("nonexistent_tool", {}, seeded_session, mem)
        assert "Unknown tool" in result

    async def test_get_sales_report(self, seeded_session):
        mem = AgentMemory(seeded_session)
        result = await execute_tool(
            "get_sales_report", {"days_back": 7}, seeded_session, mem
        )
        data = json.loads(result)
        assert "total_revenue" in data

    async def test_recall_customer(self, seeded_session):
        mem = AgentMemory(seeded_session)
        result = await execute_tool(
            "recall_customer", {"sender_id": "U_NOBODY"}, seeded_session, mem
        )
        data = json.loads(result)
        assert data["found"] is False

    async def test_record_knowledge(self, seeded_session):
        mem = AgentMemory(seeded_session)
        result = await execute_tool(
            "record_knowledge",
            {"topic": "Test", "insight": "Just testing", "keywords": "test"},
            seeded_session,
            mem,
        )
        data = json.loads(result)
        assert data["topic"] == "Test"
