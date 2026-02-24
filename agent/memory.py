"""Three-tier memory system for the Claudius agent.

Tier 1: Scratchpad — daily summaries, running notes (fast, key-value)
Tier 2: KV Store — structured data: supplier contacts, price history
Tier 3: Vector DB — semantic search over past decisions (optional, ChromaDB)
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import KVStore, Scratchpad

logger = logging.getLogger(__name__)


class AgentMemory:
    """Persistent memory backed by SQLite via SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Tier 1: Scratchpad ---

    async def write_scratchpad(self, key: str, value: str) -> None:
        existing = await self.session.get(Scratchpad, key)
        if existing:
            existing.value = value
        else:
            self.session.add(Scratchpad(key=key, value=value))
        await self.session.commit()
        logger.debug("Scratchpad write: %s", key)

    async def read_scratchpad(self, key: str) -> Optional[str]:
        entry = await self.session.get(Scratchpad, key)
        return entry.value if entry else None

    async def list_scratchpad_keys(self) -> list[dict[str, str]]:
        result = await self.session.execute(
            select(Scratchpad.key, Scratchpad.ts).order_by(Scratchpad.ts.desc())
        )
        return [{"key": row.key, "updated": str(row.ts)} for row in result]

    # --- Tier 2: KV Store ---

    async def kv_set(self, key: str, value: str) -> None:
        existing = await self.session.get(KVStore, key)
        if existing:
            existing.value = value
        else:
            self.session.add(KVStore(key=key, value=value))
        await self.session.commit()

    async def kv_get(self, key: str) -> Optional[str]:
        entry = await self.session.get(KVStore, key)
        return entry.value if entry else None
