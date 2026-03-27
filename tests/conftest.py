"""Core test fixtures: in-memory DB, test client, seed data."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base, Product, Transaction
from tests.fixtures.seed_data import INITIAL_BALANCE, SEED_PRODUCTS


@pytest.fixture
async def async_engine():
    """Fresh in-memory SQLite engine per test (complete isolation)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    """AsyncSession from the test engine."""
    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def seeded_session(async_engine):
    """Pre-populated session with 10 products + $100 balance."""
    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        for p in SEED_PRODUCTS:
            session.add(Product(**p))
        session.add(Transaction(
            type="fee",
            amount=INITIAL_BALANCE,
            balance_after=INITIAL_BALANCE,
            notes="Initial seed capital",
        ))
        await session.commit()
        yield session


@pytest.fixture
async def test_app(async_engine):
    """FastAPI app with get_session dependency overridden to use test DB."""
    from main import app
    from db.engine import get_session

    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Seed data
    async with session_factory() as session:
        for p in SEED_PRODUCTS:
            session.add(Product(**p))
        session.add(Transaction(
            type="fee",
            amount=INITIAL_BALANCE,
            balance_after=INITIAL_BALANCE,
            notes="Initial seed capital",
        ))
        await session.commit()

    async def _override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(test_app):
    """httpx AsyncClient bound to test FastAPI app (no real HTTP server)."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
