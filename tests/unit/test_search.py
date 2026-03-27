"""Tests for agent/search.py — MockSearchBackend + factory."""

import pytest
from agent.search import MockSearchBackend, SearchResult, get_search_backend, results_to_dicts

pytestmark = pytest.mark.unit


class TestMockSearchBackend:
    async def test_returns_results(self):
        backend = MockSearchBackend()
        results = await backend.search("kombucha")
        assert len(results) == 5
        assert all(isinstance(r, SearchResult) for r in results)

    async def test_max_results_limit(self):
        backend = MockSearchBackend()
        results = await backend.search("chips", max_results=3)
        assert len(results) == 3

    async def test_deterministic_for_same_query(self):
        backend = MockSearchBackend()
        r1 = await backend.search("water")
        r2 = await backend.search("water")
        assert [r.price for r in r1] == [r.price for r in r2]

    async def test_different_queries_different_prices(self):
        backend = MockSearchBackend()
        r1 = await backend.search("water")
        r2 = await backend.search("chips")
        # Prices should differ (different hash seeds)
        assert [r.price for r in r1] != [r.price for r in r2]

    async def test_results_sorted_by_price(self):
        backend = MockSearchBackend()
        results = await backend.search("energy drink")
        prices = [r.price for r in results]
        assert prices == sorted(prices)

    async def test_result_fields(self):
        backend = MockSearchBackend()
        results = await backend.search("test")
        for r in results:
            assert r.title
            assert r.price > 0
            assert r.source_url.startswith("https://")
            assert r.source == "Mock"


class TestResultsToDicts:
    async def test_converts_to_dicts(self):
        backend = MockSearchBackend()
        results = await backend.search("test", max_results=2)
        dicts = results_to_dicts(results)
        assert len(dicts) == 2
        assert isinstance(dicts[0], dict)
        assert "title" in dicts[0]
        assert "price" in dicts[0]
        assert "source_url" in dicts[0]


class TestGetSearchBackend:
    def test_default_is_mock(self):
        backend = get_search_backend()
        assert isinstance(backend, MockSearchBackend)
