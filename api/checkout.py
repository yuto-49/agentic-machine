"""Purchase/checkout endpoints — iPad-facing."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.websocket import broadcast
from db.engine import get_session
from db.models import AgentDecision, Product, Transaction

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_SINGLE_PURCHASE = 80.0


# --- Pydantic schemas ---


class CartItem(BaseModel):
    product_id: int
    quantity: int


class CheckoutRequest(BaseModel):
    items: list[CartItem]
    payment_method: str = "honor_system"  # honor_system, nfc, qr


class ProductUpdate(BaseModel):
    product_id: int
    quantity: int


class CheckoutResponse(BaseModel):
    success: bool
    total: float
    message: str
    transaction_ids: list[int]
    updated_products: list[ProductUpdate]


# --- Routes ---


@router.post("/cart/checkout", response_model=CheckoutResponse)
async def checkout(req: CheckoutRequest, session: AsyncSession = Depends(get_session)):
    """Process a purchase from the iPad."""
    total = 0.0
    transaction_ids: list[int] = []

    # Validate all items first
    for item in req.items:
        product = await session.get(Product, item.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if not product.is_active:
            raise HTTPException(status_code=400, detail=f"{product.name} is not available")
        if product.quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {product.name}: {product.quantity} available",
            )
        total += product.sell_price * item.quantity

    # Check max purchase limit
    if total > MAX_SINGLE_PURCHASE:
        raise HTTPException(
            status_code=400,
            detail=f"Purchase total ${total:.2f} exceeds maximum ${MAX_SINGLE_PURCHASE:.2f}",
        )

    # Get current balance for balance_after calculation
    balance_result = await session.execute(select(func.sum(Transaction.amount)))
    current_balance = balance_result.scalar() or 0.0

    # Process each item
    for item in req.items:
        product = await session.get(Product, item.product_id)
        product.quantity -= item.quantity
        sale_amount = product.sell_price * item.quantity
        current_balance += sale_amount

        txn = Transaction(
            type="sale",
            product_id=item.product_id,
            quantity=item.quantity,
            amount=sale_amount,
            balance_after=current_balance,
            notes=f"iPad checkout: {item.quantity}x {product.name}",
        )
        session.add(txn)
        await session.flush()
        transaction_ids.append(txn.id)

    await session.commit()
    logger.info("Checkout completed: $%.2f, %d items", total, len(req.items))

    # Broadcast stock updates via WebSocket and collect updated quantities
    updated_products: list[ProductUpdate] = []
    for item in req.items:
        product = await session.get(Product, item.product_id)
        updated_products.append(ProductUpdate(product_id=item.product_id, quantity=product.quantity))
        await broadcast({
            "type": "stock_update",
            "product_id": item.product_id,
            "quantity": product.quantity,
        })

    # Log to agent_decisions so the emulator right panel sees it
    items_summary = ", ".join(f"{i.quantity}x #{i.product_id}" for i in req.items)
    session.add(AgentDecision(
        trigger=f"iPad checkout: ${total:.2f}",
        action=f"sale({items_summary})",
        reasoning=f"Processed purchase: {items_summary}. Total: ${total:.2f}. Txn IDs: {transaction_ids}",
        was_blocked=False,
    ))
    await session.commit()

    return CheckoutResponse(
        success=True,
        total=round(total, 2),
        message=f"Purchase complete! Total: ${total:.2f}",
        transaction_ids=transaction_ids,
        updated_products=updated_products,
    )
