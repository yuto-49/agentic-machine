"""Pickup order API endpoints — iPad and NFC confirmation flow.

Routes
------
POST /api/pickup/confirm        — iPad/NFC presents pickup code → unlock door
GET  /api/pickup/status/{code}  — Poll pickup status by code
GET  /api/admin/pickups         — Admin dashboard: all pending orders
POST /api/admin/pickups/{id}/cancel  — Admin cancels a pickup
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.pickup import (
    confirm_pickup,
    expire_stale_pickups,
    get_pending_pickups,
)
from api.websocket import broadcast
from db.engine import get_session
from db.models import PickupOrder

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PickupConfirmRequest(BaseModel):
    pickup_code: str = Field(..., min_length=4, max_length=8)
    confirmed_by: str = Field(default="ipad", pattern="^(ipad|nfc|admin)$")


class PickupConfirmResponse(BaseModel):
    success: bool
    pickup_code: str
    customer_name: str
    items: list[dict]
    total: float
    picked_up_at: str
    door: str


class PickupStatusResponse(BaseModel):
    pickup_code: str
    status: str
    customer_name: str
    total: float
    items: list[dict]
    created_at: str
    expires_at: Optional[str]
    picked_up_at: Optional[str]


class PendingPickupItem(BaseModel):
    order_id: int
    pickup_code: str
    customer_name: str
    platform: Optional[str]
    items: list[dict]
    total: float
    status: str
    created_at: str
    expires_at: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/pickup/confirm", response_model=PickupConfirmResponse)
async def confirm_pickup_endpoint(
    body: PickupConfirmRequest,
    session: AsyncSession = Depends(get_session),
) -> PickupConfirmResponse:
    """Customer presents pickup code at the machine (iPad or NFC).

    Validates the code, marks the order as picked_up, and unlocks the door.
    The response tells the iPad to display a success screen.
    """
    try:
        result = await confirm_pickup(session, body.pickup_code, body.confirmed_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Notify connected iPads so any admin view refreshes
    await broadcast({
        "type": "pickup_confirmed",
        "pickup_code": body.pickup_code,
        "customer_name": result["customer_name"],
    })

    logger.info("Pickup confirmed via %s: %s", body.confirmed_by, body.pickup_code)

    return PickupConfirmResponse(
        success=True,
        pickup_code=result["pickup_code"],
        customer_name=result["customer_name"],
        items=result["items"],
        total=result["total"],
        picked_up_at=result["picked_up_at"],
        door="unlocked",
    )


@router.get("/pickup/status/{pickup_code}", response_model=PickupStatusResponse)
async def pickup_status(
    pickup_code: str,
    session: AsyncSession = Depends(get_session),
) -> PickupStatusResponse:
    """Return current status of a pickup order by code.

    Used by the customer-facing iPad to show a "waiting" or "ready" screen.
    """
    result = await session.execute(
        select(PickupOrder).where(PickupOrder.pickup_code == pickup_code.upper())
    )
    order = result.scalars().first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Pickup code {pickup_code!r} not found")

    return PickupStatusResponse(
        pickup_code=order.pickup_code,
        status=order.status,
        customer_name=order.customer_name,
        total=order.total,
        items=json.loads(order.items_json),
        created_at=order.created_at.isoformat(),
        expires_at=order.expires_at.isoformat() if order.expires_at else None,
        picked_up_at=order.picked_up_at.isoformat() if order.picked_up_at else None,
    )


@router.get("/admin/pickups", response_model=list[PendingPickupItem])
async def admin_list_pickups(
    session: AsyncSession = Depends(get_session),
) -> list[PendingPickupItem]:
    """Admin view: all pending and ready pickup orders."""
    orders = await get_pending_pickups(session)
    return [PendingPickupItem(**o) for o in orders]


@router.post("/admin/pickups/{order_id}/cancel")
async def admin_cancel_pickup(
    order_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Admin cancels a pickup order and releases reserved stock."""
    order = await session.get(PickupOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Pickup order {order_id} not found")
    if order.status in ("picked_up", "expired", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel order in status {order.status!r}")

    order.status = "cancelled"

    # Release stock back
    from db.models import Product
    items = json.loads(order.items_json)
    for item in items:
        product = await session.get(Product, item["product_id"])
        if product:
            product.quantity += item["quantity"]

    await session.commit()
    await broadcast({"type": "pickup_cancelled", "order_id": order_id, "pickup_code": order.pickup_code})
    logger.info("Pickup order %d cancelled by admin", order_id)
    return {"success": True, "order_id": order_id, "pickup_code": order.pickup_code}


@router.post("/admin/pickups/expire")
async def admin_expire_pickups(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Manually trigger expiry sweep (normally run by heartbeat cron)."""
    count = await expire_stale_pickups(session)
    return {"expired": count}
