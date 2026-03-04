"""Selective Recall — 5-channel context priming before every Claude call.

Runs all channels in parallel via asyncio.gather(). One channel failure
does not break others (return_exceptions=True).
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AgentEpisode,
    AgentKnowledge,
    CustomerProfile,
    PickupOrder,
    Product,
    Transaction,
)

logger = logging.getLogger(__name__)


async def prime_context(
    sender_id: Optional[str],
    sender_name: Optional[str],
    message: str,
    session: AsyncSession,
) -> str:
    """Run 5 recall channels and return a formatted <context> block."""
    results = await asyncio.gather(
        _recall_customer(session, sender_id, sender_name),
        _recall_episodes(session),
        _recall_knowledge(session, message),
        _recall_pending_pickups(session, sender_id),
        _recall_business_context(session),
        return_exceptions=True,
    )

    sections: list[str] = []
    channel_names = [
        "CUSTOMER PROFILE",
        "RECENT EVENTS",
        "RELATED KNOWLEDGE",
        "PENDING PICKUPS",
        "BUSINESS CONTEXT",
    ]

    for name, result in zip(channel_names, results):
        if isinstance(result, Exception):
            logger.warning("Context channel %s failed: %s", name, result)
            continue
        if result:
            sections.append(f"[{name}]\n{result}")

    if not sections:
        return ""

    return "<context>\n" + "\n\n".join(sections) + "\n</context>"


async def log_episode(
    session: AsyncSession,
    event_type: str,
    summary: str,
    sender_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """Log an event to the episode table for future recall."""
    session.add(AgentEpisode(
        event_type=event_type,
        sender_id=sender_id,
        summary=summary,
        details_json=json.dumps(details) if details else None,
    ))
    await session.commit()


# --- Channel 1: Customer Profile ---

async def _recall_customer(
    session: AsyncSession,
    sender_id: Optional[str],
    sender_name: Optional[str],
) -> str:
    if not sender_id:
        return ""

    result = await session.execute(
        select(CustomerProfile).where(CustomerProfile.sender_id == sender_id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        # Auto-create stub on first interaction
        profile = CustomerProfile(
            sender_id=sender_id,
            display_name=sender_name or "Unknown",
        )
        session.add(profile)
        await session.commit()
        return f"New customer: {sender_name or sender_id} (first interaction)"

    # Update last_seen
    profile.last_seen = datetime.utcnow()
    if sender_name and sender_name != profile.display_name:
        profile.display_name = sender_name
    await session.commit()

    lines = [f"Name: {profile.display_name}"]
    lines.append(f"Total spend: ${profile.total_spend:.2f} ({profile.purchase_count} purchases)")
    if profile.private_notes:
        lines.append(f"Notes: {profile.private_notes}")
    lines.append(f"First seen: {profile.first_seen.strftime('%Y-%m-%d') if profile.first_seen else 'unknown'}")

    return "\n".join(lines)


# --- Channel 2: Recent Episodes ---

async def _recall_episodes(session: AsyncSession) -> str:
    since = datetime.utcnow() - timedelta(hours=8)
    result = await session.execute(
        select(AgentEpisode)
        .where(AgentEpisode.timestamp >= since)
        .order_by(AgentEpisode.timestamp.asc())
        .limit(15)
    )
    episodes = result.scalars().all()
    if not episodes:
        return ""

    lines = []
    for ep in episodes:
        ts = ep.timestamp.strftime("%H:%M") if ep.timestamp else "?"
        lines.append(f"[{ts}] {ep.event_type}: {ep.summary}")
    return "\n".join(lines)


# --- Channel 3: Related Knowledge ---

async def _recall_knowledge(session: AsyncSession, message: str) -> str:
    # Extract meaningful words (3+ chars, no stopwords)
    words = set(re.findall(r"[a-zA-Z]{3,}", message.lower()))
    if not words:
        return ""

    # Query knowledge entries where keywords match any word
    result = await session.execute(
        select(AgentKnowledge).order_by(AgentKnowledge.created_at.desc()).limit(50)
    )
    all_knowledge = result.scalars().all()

    matched: list[AgentKnowledge] = []
    for k in all_knowledge:
        if not k.keywords:
            continue
        kw_set = set(kw.strip().lower() for kw in k.keywords.split(","))
        if words & kw_set:
            matched.append(k)
            if len(matched) >= 5:
                break

    if not matched:
        return ""

    lines = []
    for k in matched:
        lines.append(f"- [{k.topic}] {k.insight}")
    return "\n".join(lines)


# --- Channel 4: Pending Pickups ---

async def _recall_pending_pickups(
    session: AsyncSession,
    sender_id: Optional[str],
) -> str:
    query = select(PickupOrder).where(PickupOrder.status == "reserved")
    if sender_id:
        query = query.where(PickupOrder.sender_id == sender_id)
    query = query.order_by(PickupOrder.created_at.desc()).limit(10)

    result = await session.execute(query)
    pickups = result.scalars().all()
    if not pickups:
        return ""

    now = datetime.utcnow()
    lines = []
    for p in pickups:
        mins = max(0, int((p.expires_at - now).total_seconds() / 60)) if p.expires_at else "?"
        lines.append(f"- Code {p.code}: ${p.total_amount:.2f} for {p.customer_name} ({mins} min left)")
    return "\n".join(lines)


# --- Channel 5: Business Context ---

async def _recall_business_context(session: AsyncSession) -> str:
    lines = []

    # Cash balance
    balance_result = await session.execute(select(func.sum(Transaction.amount)))
    balance = balance_result.scalar() or 0.0
    lines.append(f"Cash balance: ${balance:.2f}")

    # Today's revenue
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    rev_result = await session.execute(
        select(func.sum(Transaction.amount))
        .where(Transaction.type == "sale")
        .where(Transaction.created_at >= today_start)
    )
    today_rev = rev_result.scalar() or 0.0
    lines.append(f"Today's revenue: ${today_rev:.2f}")

    # Low stock alerts
    low_stock = await session.execute(
        select(Product)
        .where(Product.is_active == True, Product.quantity <= 3)  # noqa: E712
        .order_by(Product.quantity.asc())
    )
    low_items = low_stock.scalars().all()
    if low_items:
        alerts = [f"{p.name} ({p.quantity} left)" for p in low_items]
        lines.append(f"Low stock: {', '.join(alerts)}")

    return "\n".join(lines)
