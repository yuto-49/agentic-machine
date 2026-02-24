"""Standalone script to initialize the database.

Run: python db/init_db.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path so imports work when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.engine import async_engine, init_db  # noqa: E402
from db.models import Base  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    logger.info("Database initialized successfully at %s", async_engine.url)
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
