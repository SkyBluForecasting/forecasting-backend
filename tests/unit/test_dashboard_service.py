"""Unit tests for the dashboard service module."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.dashboard_service import get_dashboard_asset_data
from app.db_utils import to_utc_iso


@pytest.mark.asyncio
async def test_dashboard_no_forecast():
    """If no forecasts exist, dashboard returns empty lists and measurements None."""
    with patch(
        "app.dashboard_service.get_recent_forecasts", new_callable=AsyncMock
    ) as mock_forecasts:
        mock_forecasts.return_value = []
        result = await get_dashboard_asset_data("asset123")

    assert result["asset_uuid"] == "asset123"
    assert result["latest_forecasts"] == []
    assert result["previous_forecasts"] == []
    assert result["measurements"] is None


@pytest.mark.asyncio
async def test_dashboard_forecast_no_rows():
    """If forecasts exist but no forecast rows, measurements should include units."""
    latest_forecast = {
        "forecast_run_id": "run111",
        "model_run_id": "model123",
        "asset_uuid": "asset123",
    }
    second_forecast = {
        "forecast_run_id": "run110",
        "model_run_id": "model122",
        "asset_uuid": "asset123",
    }

    with patch(
        "app.dashboard_service.get_recent_forecasts", new_callable=AsyncMock
    ) as mock_forecasts, patch(
        "app.dashboard_service.get_forecast_rows", new_callable=AsyncMock
    ) as mock_rows, patch(
        "app.dashboard_service.get_all_measurements", new_callable=AsyncMock
    ) as mock_meas:

        mock_forecasts.return_value = [latest_forecast, second_forecast]
        mock_rows.return_value = []
        mock_meas.return_value = {
            "metrics": ["load", "temp"],
            "units": {"load": "kW", "temp": "C"},
            "values": [],
        }

        result = await get_dashboard_asset_data("asset123")

    # Basic structure checks
    assert result["asset_uuid"] == "asset123"
    assert result["latest_forecasts"][0]["values"] == []
    assert result["previous_forecasts"][0]["values"] == []

    # Measurements checks
    measurements = result["measurements"]
    assert "metrics" in measurements
    assert "values" in measurements
    assert "units" in measurements

    # Check specific units
    assert measurements["units"]["load"] == "kW"
    assert measurements["units"]["temp"] == "C"


@pytest.mark.asyncio
async def test_dashboard_forecast_with_rows_and_measurements():
    """Full flow: two forecasts with rows and measurements returned."""
    latest_forecast = {
        "forecast_run_id": "run111",
        "model_run_id": "model123",
        "asset_uuid": "asset123",
    }
    second_forecast = {
        "forecast_run_id": "run110",
        "model_run_id": "model122",
        "asset_uuid": "asset123",
    }

    forecast_rows_latest = [
        {"timestamp": datetime(2025, 9, 13, 21, 0, tzinfo=timezone.utc), "forecast_kw": 50},
        {"timestamp": datetime(2025, 9, 13, 22, 0, tzinfo=timezone.utc), "forecast_kw": 55},
    ]
    forecast_rows_second = [
        {"timestamp": datetime(2025, 9, 12, 21, 0, tzinfo=timezone.utc), "forecast_kw": 40},
        {"timestamp": datetime(2025, 9, 12, 22, 0, tzinfo=timezone.utc), "forecast_kw": 45},
    ]

    measurements = {
        "metrics": ["metric1"],
        "values": [
            {"timestamp": "2025-09-13T21:00:00Z", "values": {"metric1": 100}},
            {"timestamp": "2025-09-13T22:00:00Z", "values": {"metric1": 110}},
        ],
    }

    async def mock_format(run_id):
        if run_id == "run111":
            return {
                "forecast_run_id": "run111",
                "model_run_id": "model123",
                "values": [
                    {"timestamp": to_utc_iso(r["timestamp"]), "forecast_kw": r["forecast_kw"]}
                    for r in forecast_rows_latest
                ],
            }
        else:
            return {
                "forecast_run_id": "run110",
                "model_run_id": "model122",
                "values": [
                    {"timestamp": to_utc_iso(r["timestamp"]), "forecast_kw": r["forecast_kw"]}
                    for r in forecast_rows_second
                ],
            }

    with patch(
        "app.dashboard_service.get_recent_forecasts", new_callable=AsyncMock
    ) as mock_forecasts, patch(
        "app.dashboard_service.get_forecast_rows", new_callable=AsyncMock
    ) as mock_rows, patch(
        "app.dashboard_service.get_all_measurements", new_callable=AsyncMock
    ) as mock_meas:

        mock_forecasts.return_value = [latest_forecast, second_forecast]
        # get_forecast_rows should return the correct rows depending on run_id
        mock_rows.side_effect = lambda run_id: (
            forecast_rows_latest if run_id == "run111" else forecast_rows_second
        )
        mock_meas.return_value = measurements

        result = await get_dashboard_asset_data("asset123")

    assert result["asset_uuid"] == "asset123"
    # Active forecast
    assert result["latest_forecasts"][0]["forecast_run_id"] == "run111"
    assert result["latest_forecasts"][0]["model_run_id"] == "model123"
    # Inactive forecast
    assert result["previous_forecasts"][0]["forecast_run_id"] == "run110"
    assert result["previous_forecasts"][0]["model_run_id"] == "model122"
    # Measurements
    assert result["measurements"] == measurements
