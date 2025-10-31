"""Tests for DB Client."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.db_client as db_client


@pytest.mark.asyncio
async def test_get_db_yields_session(monkeypatch):
    """Ensure get_db yields an AsyncSession instance."""
    fake_session = AsyncMock(spec=AsyncSession)

    class AsyncSessionContextManager:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(db_client, "AsyncSessionLocal", lambda: AsyncSessionContextManager())

    gen = db_client.get_db()
    session = await gen.__anext__()
    assert session is fake_session


@pytest.mark.asyncio
async def test_close_db_pool(monkeypatch):
    """Ensure engine.dispose is awaited."""
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    monkeypatch.setattr(db_client, "engine", mock_engine)

    await db_client.close_db_pool()
    mock_engine.dispose.assert_awaited_once()


def test_engine_args_for_postgres(monkeypatch):
    """Ensure PostgreSQL engine has pooling options."""
    mock_create_engine = MagicMock(return_value=MagicMock())

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/db",
    )

    with patch("sqlalchemy.ext.asyncio.create_async_engine", mock_create_engine):
        importlib.reload(db_client)

    mock_create_engine.assert_called_once()
    _, kwargs = mock_create_engine.call_args
    assert kwargs["pool_size"] == 20
    assert kwargs["max_overflow"] == 40
    assert kwargs["pool_timeout"] == 60
    assert kwargs["pool_recycle"] == 1800

    importlib.reload(db_client)


def test_engine_args_for_sqlite(monkeypatch):
    """Ensure SQLite skips pooling."""
    mock_create_engine = MagicMock(return_value=MagicMock())

    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    with patch("sqlalchemy.ext.asyncio.create_async_engine", mock_create_engine):
        importlib.reload(db_client)

    mock_create_engine.assert_called_once()
    _, kwargs = mock_create_engine.call_args
    # SQLite should not have pool arguments
    assert "pool_size" not in kwargs
    assert "max_overflow" not in kwargs
    assert "pool_timeout" not in kwargs
    assert "pool_recycle" not in kwargs

    importlib.reload(db_client)
