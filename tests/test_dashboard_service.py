"""Unit tests for the constraint service module, including formatting and DB calls."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.dashboard_service import get_dashboard_asset_data
from app.db_utils import to_utc_iso


@pytest.mark.asyncio
async def test_dashboard_no_forecast():
    """If no active forecast exists, dashboard returns None for forecast and measurements."""
    with patch(
        "app.dashboard_service.get_active_forecast", new_callable=AsyncMock
    ) as mock_forecast:
        mock_forecast.return_value = None
        result = await get_dashboard_asset_data("asset123")

    assert result["asset_uuid"] == "asset123"
    assert result["forecast"] is None
    assert result["measurements"] is None


@pytest.mark.asyncio
async def test_dashboard_forecast_no_rows():
    """If forecast exists but no forecast rows, measurements should be empty."""
    latest_forecast = {
        "forecast_uuid": "11111111-1111-1111-1111-111111111111",
        "run_uuid": "run123",
        "asset_uuid": "asset123",
    }

    with patch(
        "app.dashboard_service.get_active_forecast", new_callable=AsyncMock
    ) as mock_forecast, patch(
        "app.dashboard_service.get_forecast_rows", new_callable=AsyncMock
    ) as mock_rows, patch(
        "app.dashboard_service.get_all_measurements", new_callable=AsyncMock
    ) as mock_meas:
        mock_forecast.return_value = latest_forecast
        mock_rows.return_value = []
        # Should not be called since no start/end times
        mock_meas.return_value = {"metrics": [], "values": []}

        result = await get_dashboard_asset_data("asset123")

    assert result["asset_uuid"] == "asset123"
    assert result["forecast"]["forecast_uuid"] == latest_forecast["forecast_uuid"]
    assert result["forecast"]["values"] == []
    assert result["measurements"]["metrics"] == []
    assert result["measurements"]["values"] == []


@pytest.mark.asyncio
async def test_dashboard_forecast_with_rows_and_measurements():
    """Full flow: forecast rows exist and measurements are returned."""
    latest_forecast = {
        "forecast_uuid": "11111111-1111-1111-1111-111111111111",
        "run_uuid": "run123",
        "asset_uuid": "asset123",
    }

    forecast_rows = [
        {
            "timestamp": datetime(2025, 9, 13, 21, 0, tzinfo=timezone.utc),
            "forecast_kw": 50,
        },
        {
            "timestamp": datetime(2025, 9, 13, 22, 0, tzinfo=timezone.utc),
            "forecast_kw": 55,
        },
    ]

    measurements = {
        "metrics": ["metric1"],
        "values": [
            {"timestamp": "2025-09-13T21:00:00Z", "metric1": 100},
            {"timestamp": "2025-09-13T22:00:00Z", "metric1": 110},
        ],
    }

    with patch(
        "app.dashboard_service.get_active_forecast", new_callable=AsyncMock
    ) as mock_forecast, patch(
        "app.dashboard_service.get_forecast_rows", new_callable=AsyncMock
    ) as mock_rows, patch(
        "app.dashboard_service.get_all_measurements", new_callable=AsyncMock
    ) as mock_meas:

        mock_forecast.return_value = latest_forecast
        mock_rows.return_value = forecast_rows
        mock_meas.return_value = measurements

        result = await get_dashboard_asset_data("asset123")

    assert result["asset_uuid"] == "asset123"
    assert result["forecast"]["forecast_uuid"] == latest_forecast["forecast_uuid"]
    assert result["forecast"]["run_uuid"] == latest_forecast["run_uuid"]
    # Check that timestamps are converted to ISO
    expected_forecast = [
        {"timestamp": to_utc_iso(forecast_rows[0]["timestamp"]), "forecast_kw": 50},
        {"timestamp": to_utc_iso(forecast_rows[1]["timestamp"]), "forecast_kw": 55},
    ]
    assert result["forecast"]["values"] == expected_forecast
    assert result["measurements"] == measurements
