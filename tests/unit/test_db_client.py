"""Unit tests for the DB Client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import db_client


@pytest.mark.asyncio
async def test_close_db_pool_calls_dispose():
    """Ensure close_db_pool calls engine.dispose()."""
    # Create a mock engine with an async dispose
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    # Patch db_client.engine with the mock
    with patch("app.db_client.engine", mock_engine):
        await db_client.close_db_pool()
        mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_yields_session(monkeypatch):
    """Ensure get_db yields an AsyncSession instance."""
    mock_session = AsyncMock(spec=AsyncSession)

    class AsyncSessionContextManager:
        """Mock async context manager for AsyncSessionLocal."""

        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(db_client, "AsyncSessionLocal", lambda: AsyncSessionContextManager())

    gen = db_client.get_db()
    session = await gen.__anext__()
    assert session == mock_session
