"""Pickup reservation logic — shared by agent tools and iPad API.

Stock is reserved at ORDER time (prevents overselling between order and pickup).
30-minute expiry window. Expired reservations create compensating transactions.
"""

import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.websocket import broadcast
from db.models import AgentDecision, PickupOrder, Product, Transaction
from hardware import get_controller

logger = logging.getLogger(__name__)

PICKUP_EXPIRY_MINUTES = 30
CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_LENGTH = 6
MAX_CODE_RETRIES = 10


async def create_reservation(
    session: AsyncSession,
    items: list[dict[str, Any]],
    customer_name: str,
    sender_id: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict[str, Any]:
    """Reserve items and generate a 6-char pickup code.

    Decrements stock immediately, creates sale transactions,
    and returns a pickup code for the customer.
    """
    # Generate unique code
    code = await _generate_unique_code(session)

    total = 0.0
    transaction_ids: list[int] = []
    item_snapshots: list[dict] = []

    # Get current balance
    balance_result = await session.execute(select(func.sum(Transaction.amount)))
    current_balance = balance_result.scalar() or 0.0

    for item in items:
        product = await session.get(Product, item["product_id"])
        qty = item["quantity"]
        product.quantity -= qty
        sale_amount = product.sell_price * qty
        total += sale_amount
        current_balance += sale_amount

        txn = Transaction(
            type="sale",
            product_id=product.id,
            quantity=qty,
            amount=sale_amount,
            balance_after=current_balance,
            notes=f"Pickup reservation {code} ({customer_name}): {qty}x {product.name}",
        )
        session.add(txn)
        await session.flush()
        transaction_ids.append(txn.id)

        item_snapshots.append({
            "product_id": product.id,
            "name": product.name,
            "quantity": qty,
            "unit_price": product.sell_price,
            "subtotal": sale_amount,
        })

    expires_at = datetime.utcnow() + timedelta(minutes=PICKUP_EXPIRY_MINUTES)

    pickup = PickupOrder(
        code=code,
        status="reserved",
        items_json=json.dumps(item_snapshots),
        total_amount=total,
        transaction_ids_json=json.dumps(transaction_ids),
        sender_id=sender_id,
        customer_name=customer_name,
        platform=platform,
        expires_at=expires_at,
    )
    session.add(pickup)

    session.add(AgentDecision(
        trigger=f"Pickup reservation from {customer_name}: ${total:.2f}",
        action=f"reserve({code})",
        reasoning=f"Reserved {len(items)} items for {customer_name}. Code: {code}. Expires: {expires_at.isoformat()}",
        was_blocked=False,
    ))

    await session.commit()
    logger.info("Pickup reservation %s created for %s: $%.2f", code, customer_name, total)

    # Broadcast stock updates
    for item in items:
        product = await session.get(Product, item["product_id"])
        await broadcast({
            "type": "stock_update",
            "product_id": item["product_id"],
            "quantity": product.quantity,
        })

    return {
        "code": code,
        "total": round(total, 2),
        "items": item_snapshots,
        "expires_at": expires_at.isoformat(),
        "transaction_ids": transaction_ids,
    }


async def confirm_pickup(
    session: AsyncSession,
    code: str,
) -> dict[str, Any]:
    """Validate pickup code and unlock door.

    Returns success/error dict.
    """
    result = await session.execute(
        select(PickupOrder).where(PickupOrder.code == code.upper())
    )
    pickup = result.scalar_one_or_none()

    if pickup is None:
        return {"success": False, "error": f"Pickup code {code} not found"}

    if pickup.status == "picked_up":
        return {"success": False, "error": "This order has already been picked up"}

    if pickup.status == "expired":
        return {"success": False, "error": "This reservation has expired"}

    if pickup.status == "cancelled":
        return {"success": False, "error": "This reservation was cancelled"}

    # Check expiry
    if pickup.expires_at and datetime.utcnow() > pickup.expires_at:
        pickup.status = "expired"
        await session.commit()
        await _release_stock_for_pickup(session, pickup)
        return {"success": False, "error": "This reservation has expired"}

    # Mark as picked up
    pickup.status = "picked_up"
    pickup.picked_up_at = datetime.utcnow()
    await session.commit()

    # Unlock door
    hw = get_controller()
    hw.unlock_door()

    items = json.loads(pickup.items_json)

    await broadcast({
        "type": "pickup_confirmed",
        "code": code,
        "customer": pickup.customer_name,
        "total": pickup.total_amount,
    })

    logger.info("Pickup %s confirmed for %s", code, pickup.customer_name)

    return {
        "success": True,
        "code": code,
        "customer": pickup.customer_name,
        "items": items,
        "total": pickup.total_amount,
    }


async def expire_stale_pickups(session: AsyncSession) -> list[str]:
    """Expire all stale reservations and release stock.

    Returns list of expired codes.
    """
    now = datetime.utcnow()
    result = await session.execute(
        select(PickupOrder).where(
            PickupOrder.status == "reserved",
            PickupOrder.expires_at < now,
        )
    )
    stale = result.scalars().all()
    expired_codes: list[str] = []

    for pickup in stale:
        pickup.status = "expired"
        await session.commit()
        await _release_stock_for_pickup(session, pickup)
        expired_codes.append(pickup.code)
        logger.info("Pickup %s expired — stock released", pickup.code)

    return expired_codes


async def get_pending_pickups(
    session: AsyncSession,
    sender_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List active reservations, optionally filtered by customer."""
    query = select(PickupOrder).where(PickupOrder.status == "reserved")
    if sender_id:
        query = query.where(PickupOrder.sender_id == sender_id)
    query = query.order_by(PickupOrder.created_at.desc())

    result = await session.execute(query)
    pickups = result.scalars().all()

    now = datetime.utcnow()
    return [
        {
            "code": p.code,
            "customer": p.customer_name,
            "total": p.total_amount,
            "items": json.loads(p.items_json),
            "expires_at": p.expires_at.isoformat() if p.expires_at else None,
            "minutes_remaining": max(0, int((p.expires_at - now).total_seconds() / 60)) if p.expires_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pickups
    ]


async def _generate_unique_code(session: AsyncSession) -> str:
    """Generate a unique 6-char alphanumeric code."""
    for _ in range(MAX_CODE_RETRIES):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        existing = await session.execute(
            select(PickupOrder).where(
                PickupOrder.code == code,
                PickupOrder.status == "reserved",
            )
        )
        if existing.scalar_one_or_none() is None:
            return code
    raise RuntimeError("Failed to generate unique pickup code after max retries")


async def _release_stock_for_pickup(
    session: AsyncSession,
    pickup: PickupOrder,
) -> None:
    """Compensating transactions: restore stock and create refund records."""
    items = json.loads(pickup.items_json)

    balance_result = await session.execute(select(func.sum(Transaction.amount)))
    current_balance = balance_result.scalar() or 0.0

    for item in items:
        product = await session.get(Product, item["product_id"])
        if product is None:
            continue
        product.quantity += item["quantity"]
        refund_amount = -item["subtotal"]
        current_balance += refund_amount

        txn = Transaction(
            type="refund",
            product_id=item["product_id"],
            quantity=item["quantity"],
            amount=refund_amount,
            balance_after=current_balance,
            notes=f"Pickup {pickup.code} expired — refund {item['quantity']}x {item['name']}",
        )
        session.add(txn)

    await session.commit()

    # Broadcast stock updates
    for item in items:
        product = await session.get(Product, item["product_id"])
        if product:
            await broadcast({
                "type": "stock_update",
                "product_id": item["product_id"],
                "quantity": product.quantity,
            })
