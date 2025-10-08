"""Unit tests for measurement_service.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.measurement_service import get_all_measurements


@pytest.mark.asyncio
async def test_get_all_measurements_basic_formatting():
    """Test measurements are grouped by timestamp and metrics sorted."""
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

    # Mock the result object returned by session.execute
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = mock_rows

    # Mock the async context manager for AsyncSessionLocal
    async_mock_session = AsyncMock()
    async_mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch(
        "app.measurement_service.AsyncSessionLocal", return_value=async_mock_session
    ):
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
    assert first_value["power"] == 100.5
    assert first_value["voltage"] == 220.0


@pytest.mark.asyncio
async def test_get_all_measurements_empty():
    """Test empty measurement results return empty lists."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []

    async_mock_session = AsyncMock()
    async_mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch(
        "app.measurement_service.AsyncSessionLocal", return_value=async_mock_session
    ):
        result = await get_all_measurements(
            "asset123",
            datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 10, 7, 14, 0, tzinfo=timezone.utc),
        )

    assert result == {"metrics": [], "values": []}


@pytest.mark.asyncio
async def test_get_all_measurements_single_metric():
    """Test measurements with only one metric."""
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

    with patch(
        "app.measurement_service.AsyncSessionLocal", return_value=async_mock_session
    ):
        result = await get_all_measurements(
            "asset123",
            datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 10, 7, 13, 0, tzinfo=timezone.utc),
        )

    assert result["metrics"] == ["power"]
    assert result["values"][0]["power"] == 100.0
    assert result["values"][0]["timestamp"] == "2025-10-07T12:00:00Z"
