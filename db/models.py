"""SQLAlchemy ORM models for Claudius vending machine."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(50))  # snack, drink, specialty
    size: Mapped[Optional[str]] = mapped_column(String(20))  # small, large
    cost_price: Mapped[float] = mapped_column(Float, nullable=False)
    sell_price: Mapped[float] = mapped_column(Float, nullable=False)
    slot: Mapped[Optional[str]] = mapped_column(String(10))  # A1, A2, B1, etc.
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    max_quantity: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # sale, restock, refund, fee
    product_id: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # positive=income, negative=expense
    balance_after: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    was_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Scratchpad(Base):
    __tablename__ = "scratchpad"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
    ts: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class KVStore(Base):
    __tablename__ = "kv_store"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direction: Mapped[str] = mapped_column(String(30), nullable=False)  # customer_to_agent, agent_to_customer
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sender_id: Mapped[Optional[str]] = mapped_column(String(100))
    platform: Mapped[Optional[str]] = mapped_column(String(20))  # slack, discord, ipad, system
    channel: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserInteraction(Base):
    """Research hypothesis data collection."""
    __tablename__ = "user_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sender_id: Mapped[Optional[str]] = mapped_column(String(100))
    sender_name: Mapped[Optional[str]] = mapped_column(String(100))
    platform: Mapped[Optional[str]] = mapped_column(String(20))
    user_cohort: Mapped[Optional[str]] = mapped_column(String(50))  # cs_student, non_cs, unknown
    interaction_type: Mapped[Optional[str]] = mapped_column(String(50))  # purchase, inquiry, adversarial, etc.
    message_text: Mapped[Optional[str]] = mapped_column(Text)
    agent_response: Mapped[Optional[str]] = mapped_column(Text)
    was_successful: Mapped[Optional[bool]] = mapped_column(Boolean)
    guardrail_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProductRequest(Base):
    """Customer requests for products not currently in the vending machine."""
    __tablename__ = "product_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    estimated_price: Mapped[Optional[float]] = mapped_column(Float)
    requested_by: Mapped[Optional[str]] = mapped_column(String(100))
    platform: Mapped[Optional[str]] = mapped_column(String(20))  # slack, discord, ipad
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, approved, ordered, arrived
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class DailyMetric(Base):
    """Agent performance scorecard — one row per day."""
    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    starting_balance: Mapped[Optional[float]] = mapped_column(Float)
    ending_balance: Mapped[Optional[float]] = mapped_column(Float)
    total_revenue: Mapped[Optional[float]] = mapped_column(Float)
    total_cost: Mapped[Optional[float]] = mapped_column(Float)
    profit_margin: Mapped[Optional[float]] = mapped_column(Float)
    items_sold: Mapped[Optional[int]] = mapped_column(Integer)
    stockout_events: Mapped[Optional[int]] = mapped_column(Integer)
    adversarial_attempts: Mapped[Optional[int]] = mapped_column(Integer)
    adversarial_blocked: Mapped[Optional[int]] = mapped_column(Integer)
    total_messages: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Pickup Agent Models
# ---------------------------------------------------------------------------

class PickupOrder(Base):
    """Remote order reserved for in-person pickup at the vending machine.

    Lifecycle: pending → ready → picked_up | expired | cancelled
    """
    __tablename__ = "pickup_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pickup_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, index=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(100))   # Slack/Discord sender_id
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(20))       # slack, discord, ipad
    items_json: Mapped[str] = mapped_column(Text, nullable=False)      # JSON list of {product_id, quantity, name, unit_price}
    total: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending") # pending, ready, picked_up, expired, cancelled
    transaction_ids_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON list of transaction IDs once processed
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    picked_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class CustomerProfile(Base):
    """Per-customer persistent memory — the AnimaWorks private encapsulated identity.

    One row per unique (sender_id, platform) pair. The agent can read/write
    preferences and notes; customers cannot see or modify this directly.
    """
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    first_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    total_spent: Mapped[float] = mapped_column(Float, default=0.0)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0)
    preferences_json: Mapped[Optional[str]] = mapped_column(Text)     # JSON: {liked, disliked, dietary}
    agent_notes: Mapped[Optional[str]] = mapped_column(Text)          # Private agent observations


# ---------------------------------------------------------------------------
# AnimaWorks-inspired Private Memory: Episodes + Knowledge
# ---------------------------------------------------------------------------

class AgentEpisode(Base):
    """Episodic memory — timestamped event log (daily activity).

    Inspired by AnimaWorks Episodes: "what happened and when".
    Supports selective recall: agent searches episodes by tag or time window.
    """
    __tablename__ = "agent_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # sale, restock, pricing, customer_interaction, system
    subject: Mapped[Optional[str]] = mapped_column(String(200))          # e.g. customer_id, product_id
    content: Mapped[str] = mapped_column(Text, nullable=False)           # Human-readable event description
    tags: Mapped[Optional[str]] = mapped_column(String(500))             # Comma-separated searchable tags


class AgentKnowledge(Base):
    """Semantic memory — learned facts, rules, patterns (survives consolidation).

    Inspired by AnimaWorks Knowledge: "what I've learned from experience".
    Low-confidence entries decay; high-confidence entries persist.
    """
    __tablename__ = "agent_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)        # 0.0–1.0; entries < 0.3 are candidates for removal
    source: Mapped[Optional[str]] = mapped_column(String(100))           # what triggered this knowledge entry
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_accessed: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
