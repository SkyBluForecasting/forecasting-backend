"""Unit tests for dashboard_service.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.dashboard_service import compute_error_metrics, get_dashboard_asset_data


# -----------------------------
# Unit tests for compute_error_metrics
# -----------------------------
@pytest.mark.parametrize(
    "measurements, errors, expected_mae, expected_mape",
    [
        # normal case
        (
            {
                "metrics": ["load"],
                "values": [
                    {"timestamp": "t1", "values": {"load": 50}},
                    {"timestamp": "t2", "values": {"load": 100}},
                ],
            },
            {"t1": -5, "t2": 10},
            7.5,
            (5 / 50 + 10 / 100) / 2,
        ),
        # missing measurement
        (
            {"metrics": ["load"], "values": [{"timestamp": "t1", "values": {"load": 50}}]},
            {"t1": -5, "t2": 10},
            5,
            5 / 50,
        ),
        # empty measurements
        ({"metrics": ["load"], "values": []}, {"t1": 5}, None, None),
        # zero actual
        (
            {"metrics": ["load"], "values": [{"timestamp": "t1", "values": {"load": 0}}]},
            {"t1": 5},
            5,
            None,
        ),
        # null measurement value
        (
            {"metrics": ["load"], "values": [{"timestamp": "t1", "values": {"load": None}}]},
            {"t1": 5},
            None,
            None,
        ),
    ],
)
def test_compute_error_metrics_all_cases(measurements, errors, expected_mae, expected_mape):
    """Test compute error metrics function."""
    result = compute_error_metrics(measurements, errors)
    assert result["mae"] == expected_mae
    assert result["mape"] == expected_mape


# -----------------------------
# Tests for get_dashboard_asset_data
# -----------------------------
@pytest.mark.asyncio
async def test_dashboard_no_forecast():
    """No forecasts exist → empty lists and measurements None."""
    session = AsyncMock()

    with patch(
        "app.dashboard_service.get_recent_forecasts", new_callable=AsyncMock
    ) as mock_forecasts:
        mock_forecasts.return_value = []
        result = await get_dashboard_asset_data(session, "asset123")

    assert result["asset_uuid"] == "asset123"
    assert result["latest_forecasts"] == []
    assert result["previous_forecasts"] == []
    assert result["measurements"] is None


@pytest.mark.asyncio
async def test_dashboard_forecast_no_rows():
    """Forecasts exist but no forecast rows → measurements uses empty default (units present)."""
    session = AsyncMock()

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
        "app.dashboard_service.get_forecast_errors", new_callable=AsyncMock
    ) as mock_errors, patch(
        "app.dashboard_service.get_all_measurements", new_callable=AsyncMock
    ) as mock_meas:

        mock_forecasts.return_value = [latest_forecast, second_forecast]
        mock_rows.return_value = []  # no rows for any run
        mock_errors.return_value = {}  # no errors
        # NOTE: get_all_measurements should NOT be called because no start/end
        mock_meas.return_value = {"metrics": ["load"], "values": [], "units": {"load": "kW"}}

        result = await get_dashboard_asset_data(session, "asset123")

    # Forecast structure
    latest = result["latest_forecasts"][0]
    prev = result["previous_forecasts"][0]
    assert latest["forecast_run_id"] == "run111"
    assert prev["forecast_run_id"] == "run110"
    assert latest["values"] == []
    assert prev["values"] == []

    # Accuracy metrics exist but None
    assert latest["accuracy_metrics"]["mae"] is None
    assert latest["accuracy_metrics"]["mape"] is None

    # Measurements: default empty (since no time range)
    meas = result["measurements"]
    assert meas["metrics"] == []
    assert meas["values"] == []
    assert meas["units"]["load"] == "kW"
    assert meas["units"]["temp"] == "C"

    # And ensure we didn't call get_all_measurements
    mock_meas.assert_not_called()


@pytest.mark.asyncio
async def test_dashboard_forecast_with_rows_and_measurements():
    """Full flow: two forecasts with rows, measurements, and errors."""
    session = AsyncMock()

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
        "metrics": ["load"],
        "values": [
            {"timestamp": "2025-09-13T21:00:00Z", "values": {"load": 51}},
            {"timestamp": "2025-09-13T22:00:00Z", "values": {"load": 54}},
            {"timestamp": "2025-09-12T21:00:00Z", "values": {"load": 39}},
            {"timestamp": "2025-09-12T22:00:00Z", "values": {"load": 46}},
        ],
        "units": {"load": "kW"},
    }

    errors_latest = {
        "2025-09-13T21:00:00Z": -1,
        "2025-09-13T22:00:00Z": 1,
    }
    errors_prev = {
        "2025-09-12T21:00:00Z": 1,
        "2025-09-12T22:00:00Z": 0,
    }

    async def mock_rows(_session, run_id):
        return forecast_rows_latest if run_id == "run111" else forecast_rows_second

    async def mock_errors(_session, run_id):
        return errors_latest if run_id == "run111" else errors_prev

    async def mock_measurements(_session, asset_uuid, start_time, end_time):
        return measurements

    with patch(
        "app.dashboard_service.get_recent_forecasts", new_callable=AsyncMock
    ) as mock_forecasts, patch(
        "app.dashboard_service.get_forecast_rows", side_effect=mock_rows
    ), patch(
        "app.dashboard_service.get_all_measurements", side_effect=mock_measurements
    ), patch(
        "app.dashboard_service.get_forecast_errors", side_effect=mock_errors
    ):

        mock_forecasts.return_value = [latest_forecast, second_forecast]
        result = await get_dashboard_asset_data(session, "asset123")

    latest = result["latest_forecasts"][0]
    prev = result["previous_forecasts"][0]

    # Forecast structure
    assert latest["forecast_run_id"] == "run111"
    assert prev["forecast_run_id"] == "run110"
    assert all("timestamp" in v and "forecast_kw" in v for v in latest["values"])
    assert all("timestamp" in v and "forecast_kw" in v for v in prev["values"])

    # Accuracy metrics
    assert latest["accuracy_metrics"]["mae"] == 1.0
    assert prev["accuracy_metrics"]["mae"] == 0.5
    assert latest["accuracy_metrics"]["mape"] == pytest.approx((1 / 51 + 1 / 54) / 2)
    assert prev["accuracy_metrics"]["mape"] == pytest.approx((1 / 39 + 0 / 46) / 2)

    # Measurements structure
    meas = result["measurements"]
    assert meas["metrics"] == ["load"]
    assert meas["units"]["load"] == "kW"
    assert len(meas["values"]) == 4
