"""Product request endpoints — list and update status of online product requests."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.websocket import broadcast
from db.engine import get_session
from db.models import ProductRequest

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic schemas ---


class ProductRequestOut(BaseModel):
    id: int
    query: str
    product_name: str
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    estimated_price: Optional[float] = None
    requested_by: Optional[str] = None
    platform: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProductRequestUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


# --- Routes ---


@router.get("/requests", response_model=list[ProductRequestOut])
async def list_requests(
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List product requests, optionally filtered by status."""
    stmt = select(ProductRequest).order_by(ProductRequest.created_at.desc())
    if status:
        stmt = stmt.where(ProductRequest.status == status)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.patch("/requests/{request_id}", response_model=ProductRequestOut)
async def update_request(
    request_id: int,
    body: ProductRequestUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a product request (status, notes)."""
    req = await session.get(ProductRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")

    if body.status is not None:
        req.status = body.status
    if body.notes is not None:
        req.notes = body.notes

    await session.commit()
    await session.refresh(req)

    await broadcast({
        "type": "request_status_update",
        "request_id": req.id,
        "status": req.status,
        "notes": req.notes,
    })

    return req
