"""Unit tests for measurement_service.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.measurement_service import get_all_measurements, insert_measurements


@pytest.mark.asyncio
async def test_get_all_measurements_basic_formatting():
    """Test measurements are grouped by timestamp and metrics sorted (with 'values' dict)."""
    mock_rows = [
        {
            "timestamp": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            "metric": "power",
            "value": 100.5,
        },
        {
            "timestamp": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            "metric": "voltage",
            "value": 220.0,
        },
        {
            "timestamp": datetime(2025, 10, 7, 13, 0, tzinfo=timezone.utc),
            "metric": "power",
            "value": 105.0,
        },
    ]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = mock_rows
    async_mock_session = AsyncMock()
    async_mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch("app.measurement_service.AsyncSessionLocal", return_value=async_mock_session):
        result = await get_all_measurements(
            "asset123",
            datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 10, 7, 14, 0, tzinfo=timezone.utc),
        )

    assert "metrics" in result
    assert "values" in result
    assert result["metrics"] == ["power", "voltage"]
    assert len(result["values"]) == 2

    first_value = result["values"][0]
    assert first_value["timestamp"] == "2025-10-07T12:00:00Z"
    assert first_value["values"]["power"] == 100.5
    assert first_value["values"]["voltage"] == 220.0

    second_value = result["values"][1]
    assert second_value["timestamp"] == "2025-10-07T13:00:00Z"
    assert second_value["values"]["power"] == 105.0
    assert "voltage" not in second_value["values"]


@pytest.mark.asyncio
async def test_get_all_measurements_empty():
    """Test empty measurement results return empty lists."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []

    async_mock_session = AsyncMock()
    async_mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch("app.measurement_service.AsyncSessionLocal", return_value=async_mock_session):
        result = await get_all_measurements(
            "asset123",
            datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 10, 7, 14, 0, tzinfo=timezone.utc),
        )

    assert result == {"metrics": [], "values": []}


@pytest.mark.asyncio
async def test_get_all_measurements_single_metric():
    """Test measurements with only one metric (using 'values' dict)."""
    mock_rows = [
        {
            "timestamp": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            "metric": "power",
            "value": 100.0,
        }
    ]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = mock_rows
    async_mock_session = AsyncMock()
    async_mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch("app.measurement_service.AsyncSessionLocal", return_value=async_mock_session):
        result = await get_all_measurements(
            "asset123",
            datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 10, 7, 13, 0, tzinfo=timezone.utc),
        )

    assert result["metrics"] == ["power"]
    assert result["values"][0]["timestamp"] == "2025-10-07T12:00:00Z"
    assert result["values"][0]["values"]["power"] == 100.0


@pytest.mark.asyncio
async def test_insert_measurements_success():
    """Test successful batch insert of measurements."""
    test_rows = [
        {
            "timestamp": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            "metric": "power",
            "value": 100.0,
        },
        {
            "timestamp": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            "metric": "voltage",
            "value": 220.0,
        },
    ]

    async_mock_session = AsyncMock()
    async_mock_session.__aenter__.return_value.execute = AsyncMock()
    async_mock_session.__aenter__.return_value.commit = AsyncMock()

    with patch("app.measurement_service.AsyncSessionLocal", return_value=async_mock_session):
        result = await insert_measurements("asset123", test_rows)

    assert result["status"] == "success"
    assert result["inserted"] == 2
    async_mock_session.__aenter__.return_value.execute.assert_called_once()
    async_mock_session.__aenter__.return_value.commit.assert_called_once()


@pytest.mark.asyncio
async def test_insert_measurements_no_data():
    """Test insert_measurements returns early when list is empty."""
    result = await insert_measurements("asset123", [])
    assert result == {"status": "no data provided"}


@pytest.mark.asyncio
async def test_insert_measurements_upsert():
    """Test that duplicate measurements update existing rows instead of failing."""
    ts = datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc)
    initial_rows = [
        {"timestamp": ts, "metric": "power", "value": 100.0},
        {"timestamp": ts, "metric": "voltage", "value": 220.0},
    ]
    updated_rows = [
        {"timestamp": ts, "metric": "power", "value": 101.0},  # updated value
        {"timestamp": ts, "metric": "voltage", "value": 221.0},  # updated value
    ]

    async_mock_session = AsyncMock()
    mock_context = async_mock_session.__aenter__.return_value
    mock_context.execute = AsyncMock()
    mock_context.commit = AsyncMock()

    with patch("app.measurement_service.AsyncSessionLocal", return_value=async_mock_session):
        # first insert
        result1 = await insert_measurements("asset123", initial_rows)
        # second insert with updated values
        result2 = await insert_measurements("asset123", updated_rows)

    assert result1["status"] == "success"
    assert result2["status"] == "success"
    assert result1["inserted"] == 2
    assert result2["inserted"] == 2
    # execute and commit called twice in total
    assert mock_context.execute.call_count == 2
    assert mock_context.commit.call_count == 2
