"""Tests for agent/prompts.py — TOOL_DEFINITIONS structure validation."""

import pytest
from agent.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS

pytestmark = pytest.mark.unit


class TestToolDefinitions:
    def test_has_19_tools(self):
        assert len(TOOL_DEFINITIONS) == 19

    def test_each_tool_has_required_fields(self):
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool['name']} missing 'input_schema'"

    def test_tool_names_are_unique(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_expected_tool_names_present(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        expected = {
            "get_inventory", "set_price", "get_balance", "unlock_door",
            "send_message", "write_scratchpad", "read_scratchpad",
            "get_sales_report", "process_order", "search_product_online",
            "request_online_product", "request_restock",
            "create_pickup_reservation", "confirm_pickup", "get_pending_pickups",
            "recall_customer", "update_customer_notes", "record_knowledge",
            "expire_pickups",
        }
        assert expected.issubset(names)


class TestSystemPrompt:
    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_mentions_claudius(self):
        assert "Claudius" in SYSTEM_PROMPT

    def test_mentions_margin_rule(self):
        assert "1.3" in SYSTEM_PROMPT
