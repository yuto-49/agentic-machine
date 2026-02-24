"""Hard-coded business rule validation.

These rules are enforced at the tool execution level and CANNOT be overridden
by the LLM system prompt or user messages. They are the last line of defense.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product

logger = logging.getLogger(__name__)

# --- Constants ---
MIN_MARGIN_MULTIPLIER = 1.3   # sell_price >= cost_price * 1.3
MAX_PRICE_MULTIPLIER = 5.0    # sell_price <= cost_price * 5.0 (likely error)
MAX_DISCOUNT_PERCENT = 15     # max discount without admin override
MAX_SINGLE_PURCHASE = 80.0    # dollars
MAX_RESTOCK_QTY_PER_ITEM = 50


async def validate_action(
    tool_name: str,
    inputs: dict[str, Any],
    session: AsyncSession,
) -> dict[str, Any]:
    """Validate a tool call against hard-coded business rules.

    Returns:
        {"allowed": True, "reason": "OK"} or
        {"allowed": False, "reason": "...explanation..."}
    """

    if tool_name == "set_price":
        product = await session.get(Product, inputs["product_id"])
        if product is None:
            return {"allowed": False, "reason": "Product not found"}

        min_price = product.cost_price * MIN_MARGIN_MULTIPLIER
        if inputs["new_price"] < min_price:
            return {
                "allowed": False,
                "reason": (
                    f"Price ${inputs['new_price']:.2f} is below minimum "
                    f"${min_price:.2f} (cost ${product.cost_price:.2f} x {MIN_MARGIN_MULTIPLIER})"
                ),
            }

        max_price = product.cost_price * MAX_PRICE_MULTIPLIER
        if inputs["new_price"] > max_price:
            return {
                "allowed": False,
                "reason": (
                    f"Price ${inputs['new_price']:.2f} exceeds {MAX_PRICE_MULTIPLIER}x cost — likely an error"
                ),
            }

    if tool_name == "request_restock":
        for item in inputs.get("items", []):
            qty = item.get("quantity", 0)
            if qty > MAX_RESTOCK_QTY_PER_ITEM:
                return {
                    "allowed": False,
                    "reason": f"Restock quantity {qty} exceeds max of {MAX_RESTOCK_QTY_PER_ITEM} per item",
                }
            if qty <= 0:
                return {
                    "allowed": False,
                    "reason": f"Restock quantity must be positive, got {qty}",
                }

    if tool_name == "unlock_door":
        if not inputs.get("reason", "").strip():
            return {"allowed": False, "reason": "Door unlock requires a stated reason"}

    return {"allowed": True, "reason": "OK"}
