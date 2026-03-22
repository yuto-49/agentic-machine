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


class PickupOrder(Base):
    """Reservation-based pickup orders from Slack/Discord."""
    __tablename__ = "pickup_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(6), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="reserved")  # reserved, picked_up, expired, cancelled
    items_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: [{product_id, name, quantity, unit_price, subtotal}]
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_ids_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of Transaction IDs
    sender_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(100))
    platform: Mapped[Optional[str]] = mapped_column(String(20))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    picked_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CustomerProfile(Base):
    """Per-customer profile for selective recall."""
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    total_spend: Mapped[float] = mapped_column(Float, default=0.0)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0)
    private_notes: Mapped[Optional[str]] = mapped_column(Text)  # Agent-only, never shown to customers
    first_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentEpisode(Base):
    """Episodic memory — timestamped events for recall."""
    __tablename__ = "agent_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, server_default=func.now())
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # sale, pickup, price_change, restock, alert
    sender_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentKnowledge(Base):
    """Persistent knowledge base — business insights for future recall."""
    __tablename__ = "agent_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    insight: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[Optional[str]] = mapped_column(Text)  # Comma-separated, for LIKE matching
    source: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Scenario(Base):
    """A simulation scenario run."""
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    spec_json: Mapped[Optional[str]] = mapped_column(Text)  # ScenarioSpec as JSON
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed
    total_turns: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[Optional[str]] = mapped_column(String(30))  # deal_closed, customer_left, escalation, no_deal
    outcome_json: Mapped[Optional[str]] = mapped_column(Text)  # full outcome analysis
    seller_score: Mapped[Optional[int]] = mapped_column(Integer)  # 0-100
    final_price: Mapped[Optional[float]] = mapped_column(Float)
    product_cost: Mapped[Optional[float]] = mapped_column(Float)
    margin_achieved: Mapped[Optional[float]] = mapped_column(Float)
    tactics_used: Mapped[Optional[str]] = mapped_column(Text)  # JSON list
    training_signal: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ScenarioTurn(Base):
    """One turn in a simulation dialogue."""
    __tablename__ = "scenario_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    role_name: Mapped[str] = mapped_column(String(30), nullable=False)  # customer, seller, system
    message: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls_json: Mapped[Optional[str]] = mapped_column(Text)
    guardrail_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    guardrail_detail: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


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
