"""Pluggable online product search backends.

MVP ships with a mock backend that returns deterministic fake results.
The interface is ready to swap in Amazon PA-API or other real backends.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    price: float
    source_url: str
    image_url: str
    source: str  # e.g. "Amazon", "Mock"


class SearchBackend(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        ...


class MockSearchBackend(SearchBackend):
    """Returns deterministic fake results for any query."""

    _TEMPLATES = [
        {"suffix": "Original", "base_price": 3.49, "img": "original"},
        {"suffix": "Value Pack", "base_price": 6.99, "img": "value"},
        {"suffix": "Premium", "base_price": 8.49, "img": "premium"},
        {"suffix": "Variety Box", "base_price": 12.99, "img": "variety"},
        {"suffix": "Bulk Case (24ct)", "base_price": 24.99, "img": "bulk"},
    ]

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        # Deterministic price jitter based on query hash
        seed = int(hashlib.md5(query.lower().encode()).hexdigest()[:8], 16)
        results: list[SearchResult] = []
        for i, tmpl in enumerate(self._TEMPLATES[:max_results]):
            jitter = ((seed + i) % 100) / 100  # 0.00–0.99
            price = round(tmpl["base_price"] + jitter, 2)
            slug = query.lower().replace(" ", "-")
            results.append(
                SearchResult(
                    title=f"{query} — {tmpl['suffix']}",
                    price=price,
                    source_url=f"https://example.com/product/{slug}-{tmpl['img']}",
                    image_url=f"https://placehold.co/200x200?text={slug}",
                    source="Mock",
                )
            )
        results.sort(key=lambda r: r.price)
        return results


class AmazonPAAPIBackend(SearchBackend):
    """Stub for Amazon Product Advertising API — swap in real credentials later."""

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError(
            "Amazon PA-API backend is not yet implemented. "
            "Set search_backend='mock' in config."
        )


def get_search_backend() -> SearchBackend:
    """Factory — returns the configured search backend."""
    from config_app import settings

    if settings.search_backend == "amazon":
        return AmazonPAAPIBackend()
    return MockSearchBackend()


def results_to_dicts(results: list[SearchResult]) -> list[dict]:
    """Convert SearchResult list to JSON-serializable dicts."""
    return [asdict(r) for r in results]
