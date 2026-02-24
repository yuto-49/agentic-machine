"""Admin endpoints — dashboard, logs, analytics, restock."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_session
from db.models import AgentDecision, DailyMetric, Product, Transaction, UserInteraction

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic schemas ---


class AgentDecisionOut(BaseModel):
    id: int
    trigger: str
    action: str
    reasoning: Optional[str]
    was_blocked: bool
    created_at: str

    model_config = {"from_attributes": True}


class RestockItem(BaseModel):
    product_id: int
    quantity: int


class RestockRequest(BaseModel):
    items: list[RestockItem]


# --- Routes ---


@router.get("/logs", response_model=list[AgentDecisionOut])
async def get_logs(
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get recent agent decision logs."""
    result = await session.execute(
        select(AgentDecision).order_by(AgentDecision.created_at.desc()).limit(limit)
    )
    decisions = result.scalars().all()
    return [
        AgentDecisionOut(
            id=d.id,
            trigger=d.trigger,
            action=d.action,
            reasoning=d.reasoning,
            was_blocked=d.was_blocked,
            created_at=str(d.created_at),
        )
        for d in decisions
    ]


@router.get("/analytics")
async def get_analytics(session: AsyncSession = Depends(get_session)):
    """Sales analytics summary."""
    # Total revenue
    rev_result = await session.execute(
        select(func.sum(Transaction.amount)).where(Transaction.type == "sale")
    )
    total_revenue = rev_result.scalar() or 0.0

    # Total items sold
    sold_result = await session.execute(
        select(func.sum(Transaction.quantity)).where(Transaction.type == "sale")
    )
    total_sold = sold_result.scalar() or 0

    # Product count
    prod_result = await session.execute(
        select(func.count(Product.id)).where(Product.is_active == True)  # noqa: E712
    )
    product_count = prod_result.scalar() or 0

    return {
        "total_revenue": round(total_revenue, 2),
        "total_items_sold": total_sold,
        "active_products": product_count,
    }


@router.get("/interactions")
async def get_interactions(
    limit: int = Query(50, le=500),
    interaction_type: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """User interaction data for research hypothesis."""
    query = select(UserInteraction).order_by(UserInteraction.created_at.desc())
    if interaction_type:
        query = query.where(UserInteraction.interaction_type == interaction_type)
    query = query.limit(limit)

    result = await session.execute(query)
    interactions = result.scalars().all()

    return [
        {
            "id": i.id,
            "session_id": i.session_id,
            "platform": i.platform,
            "interaction_type": i.interaction_type,
            "message_text": i.message_text,
            "agent_response": i.agent_response,
            "guardrail_hit": i.guardrail_hit,
            "created_at": str(i.created_at),
        }
        for i in interactions
    ]


@router.get("/metrics")
async def get_metrics(
    limit: int = Query(7, le=90),
    session: AsyncSession = Depends(get_session),
):
    """Daily scorecard metrics."""
    result = await session.execute(
        select(DailyMetric).order_by(DailyMetric.date.desc()).limit(limit)
    )
    return result.scalars().all()


@router.post("/restock")
async def confirm_restock(
    req: RestockRequest,
    session: AsyncSession = Depends(get_session),
):
    """Manual restock confirmation — admin adds inventory."""
    restocked = []
    for item in req.items:
        product = await session.get(Product, item.product_id)
        if product is None:
            continue
        product.quantity = min(product.quantity + item.quantity, product.max_quantity)

        txn = Transaction(
            type="restock",
            product_id=item.product_id,
            quantity=item.quantity,
            amount=0.0,  # restocking cost tracked separately
            notes=f"Admin restock: +{item.quantity} {product.name}",
        )
        session.add(txn)
        restocked.append({"product": product.name, "new_quantity": product.quantity})

    await session.commit()
    return {"restocked": restocked}
