"""Unit tests for the DB Client."""

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_db_yields_session(monkeypatch):
    """Ensure get_db yields an AsyncSession instance."""
    # Patch AsyncSessionLocal before importing get_db
    fake_session = AsyncMock()

    class AsyncSessionContextManager:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Make sure we patch before importing db_client
    monkeypatch.setattr("app.db_client.AsyncSessionLocal", lambda: AsyncSessionContextManager())
    from app.db_client import get_db  # import after patching

    gen = get_db()
    session = await gen.__anext__()
    assert session is fake_session


@pytest.mark.asyncio
async def test_close_db_pool(monkeypatch):
    """Ensure engine.dispose is awaited."""
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    monkeypatch.setattr("app.db_client.engine", mock_engine)

    from app.db_client import close_db_pool

    await close_db_pool()
    mock_engine.dispose.assert_awaited_once()


def test_engine_args_for_postgres(monkeypatch):
    """Ensure PostgreSQL engine has pooling options."""
    # Force a fresh import of db_client
    sys.modules.pop("app.db_client", None)

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/db",
    )
    mock_create_engine = MagicMock(return_value=MagicMock())

    with patch("sqlalchemy.ext.asyncio.create_async_engine", mock_create_engine):
        import app.db_client as db_client

        importlib.reload(db_client)

    # Should be called once
    call_args = mock_create_engine.call_args
    _, kwargs = call_args
    assert kwargs["pool_size"] == 20
    assert kwargs["max_overflow"] == 40
    assert kwargs["pool_timeout"] == 60
    assert kwargs["pool_recycle"] == 1800


def test_engine_args_for_sqlite(monkeypatch):
    """Ensure SQLite skips pooling."""
    sys.modules.pop("app.db_client", None)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    mock_create_engine = MagicMock(return_value=MagicMock())

    with patch("sqlalchemy.ext.asyncio.create_async_engine", mock_create_engine):
        import app.db_client as db_client

        importlib.reload(db_client)

    _, kwargs = mock_create_engine.call_args
    # SQLite should not have pool arguments
    assert "pool_size" not in kwargs
    assert "max_overflow" not in kwargs
    assert "pool_timeout" not in kwargs
    assert "pool_recycle" not in kwargs
    assert kwargs.get("connect_args") == {"check_same_thread": False}


def test_missing_database_url():
    """Raise ValueError if DATABASE_URL is not set."""
    # Remove the module to force a clean import
    sys.modules.pop("app.db_client", None)

    # Clear env and disable load_dotenv from loading .env file
    with patch.dict("os.environ", {}, clear=True), patch(
        "dotenv.load_dotenv", lambda *a, **kw: None
    ):
        with pytest.raises(ValueError, match="DATABASE_URL environment variable not set"):
            importlib.import_module("app.db_client")
