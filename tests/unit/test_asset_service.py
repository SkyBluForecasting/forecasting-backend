"""Unit tests for the asset_service module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.asset_service import fetch_assets, upsert_assets
from app.schemas import AssetResponse


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


@pytest.mark.asyncio
async def test_fetch_assets_returns_all(monkeypatch):
    """Test that fetch_assets returns all assets when no asset_uuid is given."""
    # Create mock rows returned from DB
    mock_asset1 = AssetResponse(
        asset_uuid="uuid1",
        name="Solar Farm",
        asset_type="solar",
        capacity_kw=500,
        parent_uuid=None,
    )
    mock_asset2 = AssetResponse(
        asset_uuid="uuid2",
        name="Battery",
        asset_type="battery",
        capacity_kw=200,
        parent_uuid=None,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()

    # scalars().all() → returns list of ORM objects
    mock_result.scalars.return_value.all.return_value = [mock_asset1, mock_asset2]
    mock_session.__aenter__.return_value.execute.return_value = mock_result

    monkeypatch.setattr("app.asset_service.AsyncSessionLocal", lambda: mock_session)

    result = await fetch_assets()

    assert len(result) == 2
    assert result[0]["asset_uuid"] == "uuid1"
    assert result[1]["asset_uuid"] == "uuid2"

    mock_session.__aenter__.return_value.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_assets_filters_by_uuid(monkeypatch):
    """Test that fetch_assets filters the query when asset_uuid is provided."""
    mock_asset = AssetResponse(
        asset_uuid="uuid123",
        name="Substation A",
        asset_type="substation",
        capacity_kw=80000,
        parent_uuid=None,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()

    # scalars().all() should return a 1-item list
    mock_result.scalars.return_value.all.return_value = [mock_asset]
    mock_session.__aenter__.return_value.execute.return_value = mock_result

    monkeypatch.setattr("app.asset_service.AsyncSessionLocal", lambda: mock_session)

    result = await fetch_assets("uuid123")

    # Validate result
    assert len(result) == 1
    assert result[0]["asset_uuid"] == "uuid123"
    assert result[0]["name"] == "Substation A"

    # Assert the query executed
    mock_session.__aenter__.return_value.execute.assert_awaited_once()
