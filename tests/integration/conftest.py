"""Config file for integration tests."""

import os

import pytest_asyncio
from forecasting_db.models import Base
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app, get_session


@pytest_asyncio.fixture
async def test_engine():
    """Create and yield an async SQLAlchemy engine connected to the test database.

    This fixture also ensures required schemas exist and creates all tables
    defined in `Base.metadata`.

    Yields:
        AsyncEngine: SQLAlchemy async engine connected to the test database.
    """
    TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/test_forecasting_db"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS openstef;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS product;"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Provide an async SQLAlchemy session bound to the test engine.

    Args:
        test_engine (AsyncEngine): The test database engine fixture.

    Yields:
        AsyncSession: Async SQLAlchemy session.
    """
    AsyncSessionLocal = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(test_session):
    """Provide an `AsyncClient` for testing FastAPI endpoints.

    This client overrides the `get_session` dependency to use the test
    database session, ensuring tests run in isolation.

    Args:
        test_session (AsyncSession): The test session fixture.

    Yields:
        AsyncClient: HTTPX async client configured for the FastAPI app.
    """

    async def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def clean_db(test_session):
    """Truncate all tables in the test database before each test.

    This ensures that each test starts with a clean database state.

    Args:
        test_session (AsyncSession): The test session fixture.
    """
    await test_session.execute(text("TRUNCATE TABLE openstef.assets CASCADE;"))
    await test_session.commit()
