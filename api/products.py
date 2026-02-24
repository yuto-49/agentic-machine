"""Product catalog endpoints — iPad-facing."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_session
from db.models import Product

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic schemas ---


class ProductOut(BaseModel):
    id: int
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    size: Optional[str] = None
    sell_price: float
    slot: Optional[str] = None
    quantity: int
    max_quantity: int
    is_active: bool

    model_config = {"from_attributes": True}


# --- Routes ---


@router.get("/products", response_model=list[ProductOut])
async def list_products(session: AsyncSession = Depends(get_session)):
    """Get all active products for the iPad catalog."""
    result = await session.execute(
        select(Product).where(Product.is_active == True).order_by(Product.slot)  # noqa: E712
    )
    return result.scalars().all()


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
    """Get a single product by ID."""
    product = await session.get(Product, product_id)
    if product is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Product not found")
    return product
