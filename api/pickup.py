"""Pickup confirmation endpoints — iPad-facing."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent.pickup import confirm_pickup, expire_stale_pickups, get_pending_pickups
from db.engine import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic schemas ---


class PickupConfirmRequest(BaseModel):
    code: str


class PickupConfirmResponse(BaseModel):
    success: bool
    code: str | None = None
    customer: str | None = None
    items: list[dict[str, Any]] | None = None
    total: float | None = None
    error: str | None = None


# --- Routes ---


@router.post("/pickup/confirm", response_model=PickupConfirmResponse)
async def pickup_confirm(req: PickupConfirmRequest, session: AsyncSession = Depends(get_session)):
    """Confirm a pickup reservation from the iPad."""
    code = req.code.strip().upper()
    if len(code) != 6:
        raise HTTPException(status_code=400, detail="Pickup code must be exactly 6 characters")

    result = await confirm_pickup(session, code)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return PickupConfirmResponse(
        success=True,
        code=result["code"],
        customer=result["customer"],
        items=result["items"],
        total=result["total"],
    )


@router.get("/pickup/status/{code}")
async def pickup_status(code: str, session: AsyncSession = Depends(get_session)):
    """Check the status of a pickup reservation."""
    from sqlalchemy import select
    from db.models import PickupOrder

    result = await session.execute(
        select(PickupOrder).where(PickupOrder.code == code.upper())
    )
    pickup = result.scalar_one_or_none()
    if pickup is None:
        raise HTTPException(status_code=404, detail="Pickup code not found")

    return {
        "code": pickup.code,
        "status": pickup.status,
        "customer": pickup.customer_name,
        "total": pickup.total_amount,
        "expires_at": pickup.expires_at.isoformat() if pickup.expires_at else None,
        "picked_up_at": pickup.picked_up_at.isoformat() if pickup.picked_up_at else None,
    }


@router.get("/admin/pickups")
async def list_pending_pickups(session: AsyncSession = Depends(get_session)):
    """List all pending pickup reservations."""
    pickups = await get_pending_pickups(session)
    return {"pickups": pickups}


@router.post("/admin/pickups/expire")
async def force_expire_pickups(session: AsyncSession = Depends(get_session)):
    """Manually trigger expiry of stale pickups."""
    expired = await expire_stale_pickups(session)
    return {"expired_codes": expired, "count": len(expired)}
