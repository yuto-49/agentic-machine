"""Tests for agent/memory.py — AgentMemory scratchpad + KV store."""

import pytest
from agent.memory import AgentMemory

pytestmark = pytest.mark.unit


class TestScratchpad:
    async def test_write_and_read(self, db_session):
        mem = AgentMemory(db_session)
        await mem.write_scratchpad("today", "Sold 5 water bottles")
        value = await mem.read_scratchpad("today")
        assert value == "Sold 5 water bottles"

    async def test_read_nonexistent(self, db_session):
        mem = AgentMemory(db_session)
        value = await mem.read_scratchpad("nonexistent_key")
        assert value is None

    async def test_overwrite(self, db_session):
        mem = AgentMemory(db_session)
        await mem.write_scratchpad("today", "First note")
        await mem.write_scratchpad("today", "Updated note")
        value = await mem.read_scratchpad("today")
        assert value == "Updated note"

    async def test_list_keys(self, db_session):
        mem = AgentMemory(db_session)
        await mem.write_scratchpad("key1", "val1")
        await mem.write_scratchpad("key2", "val2")
        keys = await mem.list_scratchpad_keys()
        assert len(keys) == 2
        key_names = [k["key"] for k in keys]
        assert "key1" in key_names
        assert "key2" in key_names


class TestKVStore:
    async def test_set_and_get(self, db_session):
        mem = AgentMemory(db_session)
        await mem.kv_set("supplier_phone", "555-1234")
        value = await mem.kv_get("supplier_phone")
        assert value == "555-1234"

    async def test_get_nonexistent(self, db_session):
        mem = AgentMemory(db_session)
        value = await mem.kv_get("no_such_key")
        assert value is None

    async def test_overwrite(self, db_session):
        mem = AgentMemory(db_session)
        await mem.kv_set("supplier_phone", "555-1234")
        await mem.kv_set("supplier_phone", "555-5678")
        value = await mem.kv_get("supplier_phone")
        assert value == "555-5678"

    async def test_multiple_keys(self, db_session):
        mem = AgentMemory(db_session)
        await mem.kv_set("a", "1")
        await mem.kv_set("b", "2")
        assert await mem.kv_get("a") == "1"
        assert await mem.kv_get("b") == "2"
