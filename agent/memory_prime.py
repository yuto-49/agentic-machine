"""AnimaWorks-inspired 5-channel selective recall priming.

Philosophy (from animaworks/README.md)
---------------------------------------
"Library-style memory: agents search their archives rather than cramming
 everything into context windows."

"5-channel parallel priming: when a message arrives, the framework
 automatically triggers concurrent searches across sender profile, recent
 activity, related knowledge, skill matching, and pending tasks."

How this maps to Claudius
--------------------------
Channel 1 — Customer profile   : who is this person, purchase history, notes
Channel 2 — Recent episodes    : what happened today / this week
Channel 3 — Related knowledge  : KV store + AgentKnowledge entries matching keywords
Channel 4 — Pending pickups    : any outstanding reservations for this customer
Channel 5 — Business context   : today's revenue snapshot, low-stock alerts

The `prime_context()` coroutine runs all 5 channels concurrently with
asyncio.gather(), then formats the results into a compact context block that
is injected into the system prompt before each Claude API call.  The agent
"remembers" without needing explicit retrieval instructions.

Privacy boundary
-----------------
Each customer's profile and order data is scoped to their sender_id.
Channel 1 and 4 only surface records for the current requester, so
Customer A's data is never visible in Customer B's session.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AgentEpisode,
    AgentKnowledge,
    CustomerProfile,
    KVStore,
    PickupOrder,
    Product,
    Transaction,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual recall channels
# ---------------------------------------------------------------------------

async def _recall_customer_profile(
    session: AsyncSession, sender_id: Optional[str], platform: Optional[str]
) -> str:
    """Channel 1: Retrieve the customer's persistent profile."""
    if not sender_id:
        return ""
    result = await session.execute(
        select(CustomerProfile).where(
            CustomerProfile.sender_id == sender_id,
            CustomerProfile.platform == (platform or "slack"),
        )
    )
    profile = result.scalars().first()
    if profile is None:
        return ""

    lines = [
        f"CUSTOMER PROFILE ({sender_id})",
        f"  Name: {profile.display_name or 'unknown'}",
        f"  First seen: {profile.first_seen.strftime('%Y-%m-%d') if profile.first_seen else 'n/a'}",
        f"  Purchases: {profile.purchase_count}  |  Total spent: ${profile.total_spent:.2f}",
    ]
    if profile.preferences_json:
        try:
            prefs = json.loads(profile.preferences_json)
            if prefs:
                lines.append(f"  Preferences: {json.dumps(prefs)}")
        except (json.JSONDecodeError, TypeError):
            pass
    if profile.agent_notes:
        lines.append(f"  Notes: {profile.agent_notes}")

    return "\n".join(lines)


async def _recall_recent_episodes(
    session: AsyncSession, hours: int = 8, limit: int = 5
) -> str:
    """Channel 2: Recent episodic memory — what happened today."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await session.execute(
        select(AgentEpisode)
        .where(AgentEpisode.ts >= since)
        .order_by(AgentEpisode.ts.desc())
        .limit(limit)
    )
    episodes = result.scalars().all()
    if not episodes:
        return ""
    lines = [f"RECENT ACTIVITY (last {hours}h)"]
    for ep in reversed(episodes):
        ts = ep.ts.strftime("%H:%M") if ep.ts else "?"
        lines.append(f"  [{ts}] {ep.event_type}: {ep.content}")
    return "\n".join(lines)


async def _recall_related_knowledge(
    session: AsyncSession, keywords: list[str], limit: int = 4
) -> str:
    """Channel 3: Semantic memory — relevant KV store + AgentKnowledge entries.

    Implements lightweight keyword matching (no embedding required).
    Increments access_count to simulate active recall weighting.
    """
    if not keywords:
        return ""

    matching_knowledge: list[str] = []

    # Search AgentKnowledge
    result = await session.execute(select(AgentKnowledge))
    knowledge_rows = result.scalars().all()
    for row in knowledge_rows:
        text = f"{row.key} {row.value}".lower()
        if any(kw.lower() in text for kw in keywords):
            matching_knowledge.append(f"  [{row.key}] {row.value}")
            row.access_count += 1
            row.last_accessed = datetime.now(timezone.utc)
            if len(matching_knowledge) >= limit:
                break

    # Search KV Store for relevant entries
    kv_result = await session.execute(select(KVStore))
    kv_rows = kv_result.scalars().all()
    for row in kv_rows:
        text = f"{row.key} {row.value}".lower()
        if any(kw.lower() in text for kw in keywords):
            matching_knowledge.append(f"  [kv:{row.key}] {row.value}")
            if len(matching_knowledge) >= limit * 2:
                break

    if not matching_knowledge:
        return ""

    await session.flush()
    lines = ["RELATED KNOWLEDGE"] + matching_knowledge
    return "\n".join(lines)


async def _recall_pending_pickups_for_customer(
    session: AsyncSession, sender_id: Optional[str]
) -> str:
    """Channel 4: Any outstanding pickup orders for this customer."""
    if not sender_id:
        return ""
    result = await session.execute(
        select(PickupOrder).where(
            PickupOrder.customer_id == sender_id,
            PickupOrder.status.in_(["pending", "ready"]),
        )
    )
    orders = result.scalars().all()
    if not orders:
        return ""
    lines = ["PENDING PICKUPS FOR THIS CUSTOMER"]
    for o in orders:
        exp = o.expires_at.strftime("%Y-%m-%d %H:%M UTC") if o.expires_at else "?"
        lines.append(
            f"  Code {o.pickup_code}: ${o.total:.2f} — expires {exp} ({o.status})"
        )
    return "\n".join(lines)


async def _recall_business_context(session: AsyncSession) -> str:
    """Channel 5: Live business snapshot — revenue, low-stock, balance."""
    # Today's revenue
    today = datetime.now(timezone.utc).date()
    rev_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.type == "sale",
            Transaction.created_at >= datetime(today.year, today.month, today.day),
        )
    )
    today_revenue = rev_result.scalar() or 0.0

    # Overall balance
    bal_result = await session.execute(select(func.sum(Transaction.amount)))
    balance = bal_result.scalar() or 0.0

    # Low-stock products (quantity <= 2)
    low_result = await session.execute(
        select(Product).where(Product.is_active == True, Product.quantity <= 2)  # noqa: E712
    )
    low_stock = low_result.scalars().all()

    lines = [
        "BUSINESS CONTEXT",
        f"  Balance: ${balance:.2f}  |  Today's revenue: ${today_revenue:.2f}",
    ]
    if low_stock:
        low_names = ", ".join(f"{p.name}({p.quantity})" for p in low_stock)
        lines.append(f"  LOW STOCK WARNING: {low_names}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Keyword extraction (lightweight, no NLP dependency)
# ---------------------------------------------------------------------------

def _extract_keywords(text: str) -> list[str]:
    """Pull meaningful words from a message for knowledge search."""
    stop_words = {
        "i", "me", "my", "the", "a", "an", "is", "it", "in", "on", "at",
        "to", "of", "and", "or", "for", "with", "can", "do", "want",
        "please", "thanks", "hi", "hello", "hey",
    }
    words = text.lower().split()
    # Keep words >3 chars that aren't stop-words
    keywords = [w.strip(".,!?;:") for w in words if len(w) > 3 and w not in stop_words]
    return list(dict.fromkeys(keywords))[:8]  # deduplicate, cap at 8


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def prime_context(
    session: AsyncSession,
    trigger: str,
    sender_id: Optional[str] = None,
    platform: Optional[str] = None,
) -> str:
    """Run all 5 recall channels concurrently and return a formatted context block.

    The returned string is injected into the agent's system prompt so the
    agent has relevant memory without explicit retrieval instructions.

    Returns empty string if no relevant context was found (keeps prompts lean).
    """
    keywords = _extract_keywords(trigger)

    # All 5 channels run in parallel (AnimaWorks pattern)
    (
        ch1_customer,
        ch2_episodes,
        ch3_knowledge,
        ch4_pickups,
        ch5_business,
    ) = await asyncio.gather(
        _recall_customer_profile(session, sender_id, platform),
        _recall_recent_episodes(session),
        _recall_related_knowledge(session, keywords),
        _recall_pending_pickups_for_customer(session, sender_id),
        _recall_business_context(session),
    )

    sections = [s for s in [ch1_customer, ch2_episodes, ch3_knowledge, ch4_pickups, ch5_business] if s]

    if not sections:
        return ""

    header = "=== RECALLED CONTEXT (private, not shown to customer) ==="
    footer = "=== END RECALLED CONTEXT ==="
    return "\n".join([header] + sections + [footer])


# ---------------------------------------------------------------------------
# Memory write helpers (called from agent tools)
# ---------------------------------------------------------------------------

async def record_episode(
    session: AsyncSession,
    event_type: str,
    content: str,
    subject: Optional[str] = None,
    tags: Optional[str] = None,
) -> None:
    """Append an event to the episodic memory log."""
    session.add(
        AgentEpisode(
            event_type=event_type,
            subject=subject,
            content=content,
            tags=tags,
        )
    )
    await session.flush()


async def record_knowledge(
    session: AsyncSession,
    key: str,
    value: str,
    confidence: float = 1.0,
    source: Optional[str] = None,
) -> None:
    """Upsert a knowledge entry (learned fact / rule / pattern)."""
    result = await session.execute(
        select(AgentKnowledge).where(AgentKnowledge.key == key)
    )
    existing = result.scalars().first()
    if existing:
        existing.value = value
        existing.confidence = confidence
        existing.source = source
        existing.last_accessed = datetime.now(timezone.utc)
    else:
        session.add(
            AgentKnowledge(
                key=key,
                value=value,
                confidence=confidence,
                source=source,
            )
        )
    await session.flush()


async def update_customer_notes(
    session: AsyncSession,
    sender_id: str,
    platform: str,
    notes: str,
) -> None:
    """Overwrite private agent notes on a customer profile."""
    result = await session.execute(
        select(CustomerProfile).where(
            CustomerProfile.sender_id == sender_id,
            CustomerProfile.platform == platform,
        )
    )
    profile = result.scalars().first()
    if profile:
        profile.agent_notes = notes
        await session.flush()
    else:
        logger.warning("update_customer_notes: no profile found for %s/%s", sender_id, platform)
