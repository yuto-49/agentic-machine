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
