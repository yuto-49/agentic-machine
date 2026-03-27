"""Tests for agent/loop.py — trim_to_tokens, serialize_content, agent_step."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.loop import _serialize_content, _trim_to_tokens
from tests.fixtures.mock_claude import MockLLMProvider, MockResponse, MockTextBlock, MockToolUseBlock

pytestmark = pytest.mark.unit


class TestTrimToTokens:
    def test_within_budget(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = _trim_to_tokens(messages, 1000)
        assert len(result) == 2

    def test_trims_oldest(self):
        messages = [
            {"role": "user", "content": "x" * 400},   # ~100 tokens
            {"role": "assistant", "content": "y" * 400},  # ~100 tokens
            {"role": "user", "content": "z" * 400},   # ~100 tokens
        ]
        result = _trim_to_tokens(messages, 150)  # ~150 tokens = 600 chars, fits 1 msg
        assert len(result) < 3
        # Most recent messages kept
        assert result[-1]["content"] == "z" * 400

    def test_string_content(self):
        messages = [{"role": "user", "content": "short"}]
        result = _trim_to_tokens(messages, 100)
        assert len(result) == 1

    def test_list_content(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        result = _trim_to_tokens(messages, 100)
        assert len(result) == 1

    def test_empty_messages(self):
        result = _trim_to_tokens([], 1000)
        assert result == []


class TestSerializeContent:
    def test_text_block(self):
        blocks = [MockTextBlock(text="Hello world")]
        result = _serialize_content(blocks)
        assert result == [{"type": "text", "text": "Hello world"}]

    def test_tool_use_block(self):
        blocks = [MockToolUseBlock(
            id="toolu_001", name="get_inventory", input={},
        )]
        result = _serialize_content(blocks)
        assert result[0]["type"] == "tool_use"
        assert result[0]["name"] == "get_inventory"
        assert result[0]["id"] == "toolu_001"

    def test_mixed_blocks(self):
        blocks = [
            MockTextBlock(text="Let me check"),
            MockToolUseBlock(id="toolu_002", name="get_balance", input={}),
        ]
        result = _serialize_content(blocks)
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "tool_use"


class TestAgentStep:
    """Agent step tests with MockAnthropicClient — no real API calls."""

    async def test_simple_text_response(self, seeded_session):
        mock_provider = MockLLMProvider()
        mock_provider.queue_text("Hello! We have Water Bottle for $1.50.")

        with (
            patch("agent.loop.get_llm_provider", return_value=mock_provider),
            patch("agent.loop.async_session_factory") as mock_factory,
            patch("agent.loop._conversation_history", []),
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=seeded_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            from agent.loop import agent_step
            result = await agent_step("What drinks do you have?", metadata={
                "sender_id": "U_TEST", "sender_name": "Test", "platform": "test",
            })
            assert "Hello" in result
            assert len(mock_provider.calls) == 1

    async def test_tool_use_loop(self, seeded_session):
        mock_provider = MockLLMProvider()
        # First response: tool call
        mock_provider.queue_tool_then_text(
            tool_name="get_inventory",
            tool_input={},
            final_text="We have 10 products available!",
        )

        with (
            patch("agent.loop.get_llm_provider", return_value=mock_provider),
            patch("agent.loop.async_session_factory") as mock_factory,
            patch("agent.loop._conversation_history", []),
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=seeded_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            from agent.loop import agent_step
            result = await agent_step("What do you have?", metadata={
                "sender_id": "U_TEST", "sender_name": "Test", "platform": "test",
            })
            assert "10 products" in result
            # 2 API calls: first returns tool_use, second returns final text
            assert len(mock_provider.calls) == 2

    async def test_guardrail_blocks_tool(self, seeded_session):
        mock_provider = MockLLMProvider()
        # Try to set price below minimum
        mock_provider.queue_tool_then_text(
            tool_name="set_price",
            tool_input={"product_id": 1, "new_price": 0.10},
            final_text="I can't set that price, it's below our minimum margin.",
        )

        with (
            patch("agent.loop.get_llm_provider", return_value=mock_provider),
            patch("agent.loop.async_session_factory") as mock_factory,
            patch("agent.loop._conversation_history", []),
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=seeded_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            from agent.loop import agent_step
            result = await agent_step("Set water to $0.10", metadata={
                "sender_id": "U_TEST", "sender_name": "Test", "platform": "test",
            })
            # The guardrail should have blocked the tool call
            # Product price should remain unchanged
            product = await seeded_session.get(
                __import__("db.models", fromlist=["Product"]).Product, 1
            )
            assert product.sell_price == 1.50  # Unchanged
