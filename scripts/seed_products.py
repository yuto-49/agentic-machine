"""Seed the database with initial product data.

Run: python scripts/seed_products.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.engine import async_session_factory, init_db  # noqa: E402
from db.models import Product, Transaction  # noqa: E402

SEED_PRODUCTS = [
    # Drinks
    {"name": "Water Bottle", "sku": "DRK-001", "category": "drink", "size": "small", "cost_price": 0.50, "sell_price": 1.50, "slot": "A1", "quantity": 10, "max_quantity": 15},
    {"name": "Coca-Cola", "sku": "DRK-002", "category": "drink", "size": "small", "cost_price": 0.75, "sell_price": 2.00, "slot": "A2", "quantity": 8, "max_quantity": 12},
    {"name": "Orange Juice", "sku": "DRK-003", "category": "drink", "size": "small", "cost_price": 1.00, "sell_price": 2.50, "slot": "A3", "quantity": 6, "max_quantity": 10},
    {"name": "Energy Drink", "sku": "DRK-004", "category": "drink", "size": "small", "cost_price": 1.50, "sell_price": 3.50, "slot": "A4", "quantity": 5, "max_quantity": 8},
    # Snacks
    {"name": "Chips (Classic)", "sku": "SNK-001", "category": "snack", "size": "small", "cost_price": 0.60, "sell_price": 1.75, "slot": "B1", "quantity": 10, "max_quantity": 15},
    {"name": "Granola Bar", "sku": "SNK-002", "category": "snack", "size": "small", "cost_price": 0.80, "sell_price": 2.00, "slot": "B2", "quantity": 8, "max_quantity": 12},
    {"name": "Trail Mix", "sku": "SNK-003", "category": "snack", "size": "small", "cost_price": 1.20, "sell_price": 3.00, "slot": "B3", "quantity": 6, "max_quantity": 10},
    {"name": "Candy Bar", "sku": "SNK-004", "category": "snack", "size": "small", "cost_price": 0.50, "sell_price": 1.50, "slot": "B4", "quantity": 12, "max_quantity": 15},
    # Specialty
    {"name": "Instant Ramen Cup", "sku": "SPC-001", "category": "specialty", "size": "large", "cost_price": 0.90, "sell_price": 2.50, "slot": "C1", "quantity": 4, "max_quantity": 6},
    {"name": "Coffee (Canned)", "sku": "SPC-002", "category": "specialty", "size": "small", "cost_price": 1.00, "sell_price": 2.75, "slot": "C2", "quantity": 6, "max_quantity": 8},
]

INITIAL_BALANCE = 100.00  # Starting cash in the machine


async def seed():
    await init_db()

    async with async_session_factory() as session:
        # Check if products already exist
        from sqlalchemy import select, func
        count = (await session.execute(select(func.count(Product.id)))).scalar()
        if count > 0:
            print(f"Database already has {count} products. Skipping seed.")
            return

        for p in SEED_PRODUCTS:
            session.add(Product(**p))

        # Add initial balance as a transaction
        session.add(Transaction(
            type="fee",
            amount=INITIAL_BALANCE,
            balance_after=INITIAL_BALANCE,
            notes="Initial seed capital",
        ))

        await session.commit()
        print(f"Seeded {len(SEED_PRODUCTS)} products and ${INITIAL_BALANCE:.2f} initial balance.")


if __name__ == "__main__":
    asyncio.run(seed())
