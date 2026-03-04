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
MAX_ONLINE_ORDER_PRICE = 150.0
MAX_CUSTOMER_NOTES_LENGTH = 500
MAX_KNOWLEDGE_INSIGHT_LENGTH = 1000


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

    if tool_name == "process_order":
        items = inputs.get("items", [])
        if not items:
            return {"allowed": False, "reason": "Order must contain at least one item"}

        total = 0.0
        for item in items:
            qty = item.get("quantity", 0)
            if qty <= 0:
                return {
                    "allowed": False,
                    "reason": f"Item quantity must be positive, got {qty}",
                }

            product = await session.get(Product, item["product_id"])
            if product is None:
                return {
                    "allowed": False,
                    "reason": f"Product {item['product_id']} not found",
                }
            if not product.is_active:
                return {
                    "allowed": False,
                    "reason": f"{product.name} is not currently available",
                }
            if product.quantity < qty:
                return {
                    "allowed": False,
                    "reason": f"Insufficient stock for {product.name}: {product.quantity} available, requested {qty}",
                }
            total += product.sell_price * qty

        if total > MAX_SINGLE_PURCHASE:
            return {
                "allowed": False,
                "reason": f"Order total ${total:.2f} exceeds maximum ${MAX_SINGLE_PURCHASE:.2f}",
            }

    if tool_name == "create_pickup_reservation":
        items = inputs.get("items", [])
        if not items:
            return {"allowed": False, "reason": "Reservation must contain at least one item"}

        total = 0.0
        for item in items:
            qty = item.get("quantity", 0)
            if qty <= 0:
                return {"allowed": False, "reason": f"Item quantity must be positive, got {qty}"}

            product = await session.get(Product, item["product_id"])
            if product is None:
                return {"allowed": False, "reason": f"Product {item['product_id']} not found"}
            if not product.is_active:
                return {"allowed": False, "reason": f"{product.name} is not currently available"}
            if product.quantity < qty:
                return {
                    "allowed": False,
                    "reason": f"Insufficient stock for {product.name}: {product.quantity} available, requested {qty}",
                }
            total += product.sell_price * qty

        if total > MAX_SINGLE_PURCHASE:
            return {
                "allowed": False,
                "reason": f"Order total ${total:.2f} exceeds maximum ${MAX_SINGLE_PURCHASE:.2f}",
            }

    if tool_name == "confirm_pickup":
        code = inputs.get("code", "")
        if len(code) != 6:
            return {"allowed": False, "reason": "Pickup code must be exactly 6 characters"}

    if tool_name == "update_customer_notes":
        notes = inputs.get("notes", "")
        if len(notes) > MAX_CUSTOMER_NOTES_LENGTH:
            return {
                "allowed": False,
                "reason": f"Notes ({len(notes)} chars) exceed max of {MAX_CUSTOMER_NOTES_LENGTH}",
            }

    if tool_name == "record_knowledge":
        if not inputs.get("topic", "").strip():
            return {"allowed": False, "reason": "Topic must not be empty"}
        if not inputs.get("keywords", "").strip():
            return {"allowed": False, "reason": "Keywords must not be empty"}
        insight = inputs.get("insight", "")
        if len(insight) > MAX_KNOWLEDGE_INSIGHT_LENGTH:
            return {
                "allowed": False,
                "reason": f"Insight ({len(insight)} chars) exceeds max of {MAX_KNOWLEDGE_INSIGHT_LENGTH}",
            }

    if tool_name == "request_online_product":
        price = inputs.get("estimated_price", 0)
        if price <= 0:
            return {"allowed": False, "reason": "Estimated price must be positive"}
        if price > MAX_ONLINE_ORDER_PRICE:
            return {
                "allowed": False,
                "reason": f"Estimated price ${price:.2f} exceeds maximum ${MAX_ONLINE_ORDER_PRICE:.2f}",
            }
        if not inputs.get("product_name", "").strip():
            return {"allowed": False, "reason": "Product name must not be empty"}
        if not inputs.get("source_url", "").strip():
            return {"allowed": False, "reason": "Source URL must not be empty"}

    return {"allowed": True, "reason": "OK"}
