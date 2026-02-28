"""Tool execution implementations for the Claudius agent.

Each function corresponds to a tool the agent can call. All functions
receive a SQLAlchemy AsyncSession and return a string result.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.memory import AgentMemory
from api.websocket import broadcast
from db.models import AgentDecision, Product, Transaction
from hardware import get_controller

logger = logging.getLogger(__name__)

# Lazy-init hardware controller (mocked on Windows)
_hw = None


def _get_hw():
    global _hw
    if _hw is None:
        _hw = get_controller()
    return _hw


async def tool_get_inventory(session: AsyncSession) -> str:
    """Return all active products with quantities and prices."""
    result = await session.execute(
        select(Product).where(Product.is_active == True).order_by(Product.slot)  # noqa: E712
    )
    products = result.scalars().all()
    data = [
        {
            "id": p.id,
            "name": p.name,
            "slot": p.slot,
            "category": p.category,
            "sell_price": p.sell_price,
            "cost_price": p.cost_price,
            "quantity": p.quantity,
            "max_quantity": p.max_quantity,
        }
        for p in products
    ]
    return json.dumps(data, indent=2)


async def tool_set_price(session: AsyncSession, product_id: int, new_price: float) -> str:
    """Update sell price for a product. Guardrails are checked before this is called."""
    product = await session.get(Product, product_id)
    if product is None:
        return f"Product {product_id} not found"

    old_price = product.sell_price
    product.sell_price = new_price
    await session.commit()
    return f"Price updated: {product.name} ${old_price:.2f} -> ${new_price:.2f}"


async def tool_get_balance(session: AsyncSession) -> str:
    """Get current balance and recent transaction summary."""
    # Sum all transaction amounts for balance
    result = await session.execute(select(func.sum(Transaction.amount)))
    balance = result.scalar() or 0.0

    # Last 10 transactions
    recent = await session.execute(
        select(Transaction).order_by(Transaction.created_at.desc()).limit(10)
    )
    txns = recent.scalars().all()
    txn_list = [
        {
            "type": txn.type,
            "amount": txn.amount,
            "notes": txn.notes,
            "date": str(txn.created_at),
        }
        for txn in txns
    ]
    return json.dumps({"balance": round(balance, 2), "recent_transactions": txn_list}, indent=2)


async def tool_unlock_door(reason: str) -> str:
    """Unlock the vending machine door."""
    hw = _get_hw()
    hw.unlock_door()
    return f"Door unlocked. Reason: {reason}"


async def tool_send_message(message: str, channel: str) -> str:
    """Send a message to Slack/Discord via OpenClaw."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:18789/api/send",
                json={"channel": channel, "text": message},
                timeout=10.0,
            )
            resp.raise_for_status()
        return f"Message sent to {channel}"
    except httpx.HTTPError as e:
        logger.warning("Failed to send message via OpenClaw: %s", e)
        return f"Message delivery failed: {e}"


async def tool_get_sales_report(session: AsyncSession, days_back: int) -> str:
    """Get sales data for the last N days."""
    since = datetime.utcnow() - timedelta(days=days_back)
    result = await session.execute(
        select(Transaction)
        .where(Transaction.type == "sale")
        .where(Transaction.created_at >= since)
        .order_by(Transaction.created_at.desc())
    )
    sales = result.scalars().all()

    total_revenue = sum(s.amount for s in sales)
    total_items = sum(s.quantity or 0 for s in sales)

    return json.dumps(
        {
            "period_days": days_back,
            "total_revenue": round(total_revenue, 2),
            "total_items_sold": total_items,
            "transaction_count": len(sales),
        },
        indent=2,
    )


async def tool_process_order(
    session: AsyncSession, items: list[dict], customer_name: str
) -> str:
    """Process a purchase order from Slack/Discord.

    Guardrails (stock, active status, $80 limit) are validated before this is called.
    """
    total = 0.0
    transaction_ids: list[int] = []

    # Get current balance for balance_after calculation
    balance_result = await session.execute(select(func.sum(Transaction.amount)))
    current_balance = balance_result.scalar() or 0.0

    purchased: list[dict] = []
    for item in items:
        product = await session.get(Product, item["product_id"])
        product.quantity -= item["quantity"]
        sale_amount = product.sell_price * item["quantity"]
        total += sale_amount
        current_balance += sale_amount

        txn = Transaction(
            type="sale",
            product_id=item["product_id"],
            quantity=item["quantity"],
            amount=sale_amount,
            balance_after=current_balance,
            notes=f"Agent order ({customer_name}): {item['quantity']}x {product.name}",
        )
        session.add(txn)
        await session.flush()
        transaction_ids.append(txn.id)

        purchased.append({
            "product_id": product.id,
            "name": product.name,
            "quantity": item["quantity"],
            "unit_price": product.sell_price,
            "subtotal": sale_amount,
            "remaining_stock": product.quantity,
        })

    # Log agent decision
    items_summary = ", ".join(f"{i['quantity']}x #{i['product_id']}" for i in items)
    session.add(AgentDecision(
        trigger=f"Slack order from {customer_name}: ${total:.2f}",
        action=f"sale({items_summary})",
        reasoning=f"Processed order for {customer_name}: {items_summary}. Total: ${total:.2f}. Txn IDs: {transaction_ids}",
        was_blocked=False,
    ))

    await session.commit()
    logger.info("Agent order processed for %s: $%.2f, %d items", customer_name, total, len(items))

    # Broadcast stock updates via WebSocket
    for item in items:
        product = await session.get(Product, item["product_id"])
        await broadcast({
            "type": "stock_update",
            "product_id": item["product_id"],
            "quantity": product.quantity,
        })

    return json.dumps({
        "success": True,
        "total": round(total, 2),
        "customer": customer_name,
        "items": purchased,
        "transaction_ids": transaction_ids,
    }, indent=2)


async def tool_request_restock(items: list[dict], urgency: str) -> str:
    """Submit a restock request to the admin channel."""
    # Format the request and send via OpenClaw
    item_lines = [f"  - Product #{i['product_id']}: {i['quantity']} units" for i in items]
    message = f"RESTOCK REQUEST ({urgency.upper()} urgency):\n" + "\n".join(item_lines)
    await tool_send_message(message, "slack")
    return f"Restock request submitted ({urgency} urgency, {len(items)} items)"


async def execute_tool(
    name: str,
    inputs: dict[str, Any],
    session: AsyncSession,
    memory: AgentMemory,
) -> str:
    """Route a tool call to its implementation.

    Guardrails are validated BEFORE this function is called (in the agent loop).
    """
    if name == "get_inventory":
        return await tool_get_inventory(session)
    elif name == "set_price":
        return await tool_set_price(session, inputs["product_id"], inputs["new_price"])
    elif name == "get_balance":
        return await tool_get_balance(session)
    elif name == "unlock_door":
        return await tool_unlock_door(inputs["reason"])
    elif name == "send_message":
        return await tool_send_message(inputs["message"], inputs["channel"])
    elif name == "write_scratchpad":
        await memory.write_scratchpad(inputs["key"], inputs["value"])
        return f"Saved to scratchpad: {inputs['key']}"
    elif name == "read_scratchpad":
        value = await memory.read_scratchpad(inputs["key"])
        return value or "(empty)"
    elif name == "get_sales_report":
        return await tool_get_sales_report(session, inputs["days_back"])
    elif name == "process_order":
        return await tool_process_order(session, inputs["items"], inputs["customer_name"])
    elif name == "request_restock":
        return await tool_request_restock(inputs["items"], inputs["urgency"])
    else:
        return f"Unknown tool: {name}"
