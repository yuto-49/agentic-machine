"""Pickup Agent — remote order reservation and in-person collection flow.

Architecture
------------
Customers place orders via Slack/Discord without touching the machine.
The agent creates a PickupOrder with a unique code, reduces stock (reserves
inventory), and notifies the customer.  When the customer arrives, they enter
or scan the code on the iPad (or show it to the NFC reader); the machine
confirms the reservation and unlocks/dispenses.

Lifecycle
---------
  pending   → agent has reserved stock, customer notified of code
  ready     → admin/heartbeat confirmed physical items are loaded & waiting
  picked_up → customer confirmed at machine, door unlocked
  expired   → TTL elapsed without pickup (stock released back)
  cancelled → agent or admin explicitly cancelled

Design notes
------------
- Stock is reserved (decremented) at reservation time, not at pickup time.
  This prevents overselling between order creation and pickup.
- Expiry releases the stock back via a compensating transaction so ledger
  remains consistent.
- All mutations are audit-logged to AgentDecision and AgentEpisode.
"""

import json
import logging
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AgentDecision,
    AgentEpisode,
    CustomerProfile,
    PickupOrder,
    Product,
    Transaction,
)

logger = logging.getLogger(__name__)

PICKUP_CODE_CHARS = string.ascii_uppercase + string.digits
PICKUP_CODE_LENGTH = 6
PICKUP_TTL_HOURS = 24


def _generate_code() -> str:
    """Return a random 6-character alphanumeric pickup code (uppercase)."""
    return "".join(random.choices(PICKUP_CODE_CHARS, k=PICKUP_CODE_LENGTH))


async def _unique_code(session: AsyncSession) -> str:
    """Generate a pickup code guaranteed to be unique in the DB."""
    for _ in range(10):
        code = _generate_code()
        existing = await session.execute(
            select(PickupOrder).where(PickupOrder.pickup_code == code)
        )
        if existing.scalars().first() is None:
            return code
    raise RuntimeError("Failed to generate a unique pickup code after 10 attempts")


async def _upsert_customer_profile(
    session: AsyncSession,
    sender_id: str,
    platform: str,
    display_name: str,
    spent: float,
) -> None:
    """Update or create a customer profile after a purchase."""
    result = await session.execute(
        select(CustomerProfile).where(
            CustomerProfile.sender_id == sender_id,
            CustomerProfile.platform == platform,
        )
    )
    profile = result.scalars().first()
    if profile:
        profile.display_name = display_name
        profile.last_seen = datetime.now(timezone.utc)
        profile.total_spent += spent
        profile.purchase_count += 1
    else:
        profile = CustomerProfile(
            sender_id=sender_id,
            platform=platform,
            display_name=display_name,
            total_spent=spent,
            purchase_count=1,
        )
        session.add(profile)


async def create_reservation(
    session: AsyncSession,
    customer_id: str,
    customer_name: str,
    platform: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reserve inventory for a remote pickup order.

    Args:
        session: DB session.
        customer_id: Platform-specific user ID (Slack UID, Discord UID, etc.).
        customer_name: Display name for the pickup slip.
        platform: "slack" | "discord" | "ipad".
        items: List of {"product_id": int, "quantity": int}.

    Returns:
        Dict with pickup_code, total, items detail, and expires_at.

    Raises:
        ValueError: If any item is unavailable or over stock.
    """
    # --- Validate & fetch products ---
    order_items: list[dict[str, Any]] = []
    total = 0.0
    current_balance_result = await session.execute(
        select(func.sum(Transaction.amount))
    )
    current_balance = current_balance_result.scalar() or 0.0

    for req in items:
        product = await session.get(Product, req["product_id"])
        if product is None:
            raise ValueError(f"Product {req['product_id']} not found")
        if not product.is_active:
            raise ValueError(f"{product.name} is not currently available")
        qty = req["quantity"]
        if product.quantity < qty:
            raise ValueError(
                f"Insufficient stock for {product.name}: "
                f"{product.quantity} available, requested {qty}"
            )
        subtotal = product.sell_price * qty
        total += subtotal
        order_items.append(
            {
                "product_id": product.id,
                "name": product.name,
                "slot": product.slot,
                "quantity": qty,
                "unit_price": product.sell_price,
                "subtotal": subtotal,
            }
        )

    # --- Reserve stock (decrement quantities) ---
    transaction_ids: list[int] = []
    for item in order_items:
        product = await session.get(Product, item["product_id"])
        product.quantity -= item["quantity"]
        current_balance += item["subtotal"]

        txn = Transaction(
            type="sale",
            product_id=item["product_id"],
            quantity=item["quantity"],
            amount=item["subtotal"],
            balance_after=current_balance,
            notes=f"Pickup reservation ({customer_name}): {item['quantity']}x {item['name']}",
        )
        session.add(txn)
        await session.flush()
        transaction_ids.append(txn.id)

    # --- Create PickupOrder ---
    code = await _unique_code(session)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=PICKUP_TTL_HOURS)

    order = PickupOrder(
        pickup_code=code,
        customer_id=customer_id,
        customer_name=customer_name,
        platform=platform,
        items_json=json.dumps(order_items),
        total=round(total, 2),
        status="pending",
        transaction_ids_json=json.dumps(transaction_ids),
        expires_at=expires_at,
    )
    session.add(order)

    # --- Update customer profile ---
    await _upsert_customer_profile(
        session, customer_id, platform, customer_name, total
    )

    # --- Audit logs ---
    items_summary = ", ".join(f"{i['quantity']}x {i['name']}" for i in order_items)
    session.add(
        AgentDecision(
            trigger=f"Pickup reservation request from {customer_name}",
            action=f"create_pickup_reservation({code}, [{items_summary}])",
            reasoning=f"Reserved {items_summary} for {customer_name}. Code: {code}. Total: ${total:.2f}. Expires: {expires_at.isoformat()}",
            was_blocked=False,
        )
    )
    session.add(
        AgentEpisode(
            event_type="pickup_created",
            subject=customer_id,
            content=f"Pickup order {code} created for {customer_name}: {items_summary} (${total:.2f}). Expires {expires_at.strftime('%Y-%m-%d %H:%M UTC')}.",
            tags=f"pickup,{platform},{customer_id}",
        )
    )

    await session.commit()
    await session.refresh(order)
    logger.info("Pickup reservation %s created for %s ($%.2f)", code, customer_name, total)

    return {
        "pickup_code": code,
        "customer_name": customer_name,
        "total": round(total, 2),
        "items": order_items,
        "expires_at": expires_at.isoformat(),
        "status": "pending",
        "order_id": order.id,
    }


async def confirm_pickup(
    session: AsyncSession,
    pickup_code: str,
    confirmed_by: str = "ipad",
) -> dict[str, Any]:
    """Confirm a customer has arrived and collected their order.

    This is called by the iPad/NFC reader when the customer presents their code.
    It marks the order as picked_up and triggers door unlock via the hardware
    controller (caller is responsible for the actual unlock call).

    Args:
        session: DB session.
        pickup_code: The 6-character code from the customer.
        confirmed_by: Who triggered confirmation ("ipad", "nfc", "admin").

    Returns:
        Dict with order details and success flag.

    Raises:
        ValueError: If code is invalid, expired, or already used.
    """
    result = await session.execute(
        select(PickupOrder).where(PickupOrder.pickup_code == pickup_code.upper())
    )
    order = result.scalars().first()

    if order is None:
        raise ValueError(f"Pickup code {pickup_code!r} not found")

    if order.status == "picked_up":
        raise ValueError(f"Order {pickup_code} has already been collected")

    if order.status == "cancelled":
        raise ValueError(f"Order {pickup_code} was cancelled")

    if order.status == "expired":
        raise ValueError(f"Order {pickup_code} has expired")

    now = datetime.now(timezone.utc)
    if order.expires_at and order.expires_at.replace(tzinfo=timezone.utc) < now:
        order.status = "expired"
        await session.commit()
        raise ValueError(f"Order {pickup_code} expired at {order.expires_at.isoformat()}")

    # Mark as collected
    order.status = "picked_up"
    order.picked_up_at = now

    items = json.loads(order.items_json)
    items_summary = ", ".join(f"{i['quantity']}x {i['name']}" for i in items)

    session.add(
        AgentDecision(
            trigger=f"Pickup confirmation for order {pickup_code} by {confirmed_by}",
            action=f"confirm_pickup({pickup_code})",
            reasoning=f"{customer_name_from(order)} collected {items_summary} (${order.total:.2f}) via {confirmed_by}.",
            was_blocked=False,
        )
    )
    session.add(
        AgentEpisode(
            event_type="pickup_confirmed",
            subject=order.customer_id,
            content=f"Pickup {pickup_code} collected by {order.customer_name}: {items_summary} (${order.total:.2f}). Confirmed via {confirmed_by}.",
            tags=f"pickup,{order.platform},{order.customer_id},collected",
        )
    )

    await session.commit()
    logger.info("Pickup %s confirmed for %s", pickup_code, order.customer_name)

    return {
        "success": True,
        "pickup_code": pickup_code,
        "customer_name": order.customer_name,
        "items": items,
        "total": order.total,
        "picked_up_at": now.isoformat(),
    }


def customer_name_from(order: PickupOrder) -> str:
    return order.customer_name or order.customer_id or "unknown"


async def get_pending_pickups(session: AsyncSession) -> list[dict[str, Any]]:
    """Return all non-terminal pickup orders."""
    result = await session.execute(
        select(PickupOrder)
        .where(PickupOrder.status.in_(["pending", "ready"]))
        .order_by(PickupOrder.created_at.asc())
    )
    orders = result.scalars().all()
    return [
        {
            "order_id": o.id,
            "pickup_code": o.pickup_code,
            "customer_name": o.customer_name,
            "platform": o.platform,
            "items": json.loads(o.items_json),
            "total": o.total,
            "status": o.status,
            "created_at": o.created_at.isoformat(),
            "expires_at": o.expires_at.isoformat() if o.expires_at else None,
        }
        for o in orders
    ]


async def expire_stale_pickups(session: AsyncSession) -> int:
    """Mark expired pending orders and release stock back to inventory.

    Called by the heartbeat cron job.  Returns number of orders expired.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(PickupOrder).where(
            PickupOrder.status.in_(["pending", "ready"]),
            PickupOrder.expires_at < now,
        )
    )
    stale = result.scalars().all()
    if not stale:
        return 0

    current_balance_result = await session.execute(select(func.sum(Transaction.amount)))
    current_balance = current_balance_result.scalar() or 0.0

    for order in stale:
        order.status = "expired"
        items = json.loads(order.items_json)

        # Compensating transactions to release reserved stock
        for item in items:
            product = await session.get(Product, item["product_id"])
            if product:
                product.quantity += item["quantity"]
                refund_amount = -(item["unit_price"] * item["quantity"])
                current_balance += refund_amount
                session.add(
                    Transaction(
                        type="refund",
                        product_id=item["product_id"],
                        quantity=item["quantity"],
                        amount=refund_amount,
                        balance_after=current_balance,
                        notes=f"Auto-release: pickup {order.pickup_code} expired",
                    )
                )

        session.add(
            AgentEpisode(
                event_type="pickup_expired",
                subject=order.customer_id,
                content=f"Pickup {order.pickup_code} expired for {order.customer_name}. Stock released.",
                tags=f"pickup,expired,{order.platform}",
            )
        )
        logger.info("Pickup %s expired for %s — stock released", order.pickup_code, order.customer_name)

    await session.commit()
    return len(stale)
