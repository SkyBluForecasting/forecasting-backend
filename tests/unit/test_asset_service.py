"""Unit tests for the asset_service module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.asset_service import upsert_assets


class MockAsset:
    """Simple mock class to simulate AssetIn objects."""

    def __init__(self, id, name, type, capacity_kw):
        """Initialize with a set of keys."""
        self.id = id
        self.name = name
        self.type = type
        self.capacity_kw = capacity_kw


@pytest.mark.asyncio
async def test_upsert_assets_executes_insert_and_commit(monkeypatch):
    """Test that upsert_assets executes the insert and commits successfully."""
    mock_assets = [
        MockAsset("uuid1", "Solar Farm", "solar", 500),
        MockAsset("uuid2", "Battery", "battery", 200),
    ]

    # Mock session context manager
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 2
    mock_session.__aenter__.return_value.execute.return_value = mock_result
    monkeypatch.setattr("app.asset_service.AsyncSessionLocal", lambda: mock_session)

    # Call the service
    result = await upsert_assets(mock_assets)

    # Assert the session was used correctly
    mock_session.__aenter__.return_value.execute.assert_awaited_once()
    mock_session.__aenter__.return_value.commit.assert_awaited_once()
    assert result == {"inserted": 2, "updated": 0, "total": 2}


@pytest.mark.asyncio
async def test_upsert_assets_handles_empty_input(monkeypatch):
    """Test that upsert_assets still runs but inserts 0 assets when given empty input."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.__aenter__.return_value.execute.return_value = mock_result
    monkeypatch.setattr("app.asset_service.AsyncSessionLocal", lambda: mock_session)

    result = await upsert_assets([])

    mock_session.__aenter__.return_value.execute.assert_awaited_once()
    mock_session.__aenter__.return_value.commit.assert_awaited_once()
    assert result == {"inserted": 0, "updated": 0, "total": 0}


@pytest.mark.asyncio
async def test_upsert_assets_logs_info(monkeypatch, caplog):
    """Test that upsert_assets logs info about upserted assets."""
    mock_assets = [MockAsset("uuid1", "Solar", "solar", 100)]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.__aenter__.return_value.execute.return_value = mock_result
    monkeypatch.setattr("app.asset_service.AsyncSessionLocal", lambda: mock_session)

    caplog.set_level("INFO")  # Ensure INFO logs are captured
    result = await upsert_assets(mock_assets)

    assert any("Upserted 1 assets" in msg for msg in caplog.messages), caplog.messages
    assert result == {"inserted": 1, "updated": 0, "total": 1}
