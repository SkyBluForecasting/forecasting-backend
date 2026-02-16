"""Unit tests for measurement_service.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.measurement_service import (
    _compute_forecast_errors,
    _insert_forecast_errors_for_new_measurements,
    get_all_measurements,
    insert_measurements,
)

# -----------------------------
# Fixtures
# -----------------------------


@pytest.fixture
def session():
    """Async Session mock."""
    s = AsyncMock()
    s.execute = AsyncMock()
    s.commit = AsyncMock()
    return s


# -----------------------------
# get_all_measurements tests
# -----------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_rows, expected_metrics, expected_values_len",
    [
        (
            [
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
            ],
            ["power", "voltage"],
            2,
        ),
        ([], [], 0),
        (
            [
                {
                    "timestamp": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
                    "metric": "power",
                    "value": 100.0,
                },
            ],
            ["power", "voltage"],
            1,
        ),
    ],
)
async def test_get_all_measurements_formats(
    session, mock_rows, expected_metrics, expected_values_len
):
    """Test measurements grouping and units handling."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = mock_rows
    session.execute.return_value = mock_result

    with patch("app.measurement_service.METRIC_UNITS", {"power": "kW", "voltage": "V"}):
        result = await get_all_measurements(
            session,
            "asset123",
            datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 10, 7, 14, 0, tzinfo=timezone.utc),
        )

    assert set(result.keys()) == {"metrics", "values", "units"}
    assert result["metrics"] == expected_metrics
    assert len(result["values"]) == expected_values_len


# -----------------------------
# insert_measurements tests
# -----------------------------


@pytest.mark.asyncio
async def test_insert_measurements(session):
    """Test insert_measurements inserts and commits."""
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

    # insert_measurements calls _insert_forecast_errors_for_new_measurements internally
    with patch(
        "app.measurement_service._insert_forecast_errors_for_new_measurements",
        new_callable=AsyncMock,
    ) as mock_insert_errors:
        result = await insert_measurements(session, "asset123", test_rows)

    assert result["status"] == "success"
    assert result["inserted"] == 2
    session.execute.assert_awaited()
    session.commit.assert_awaited()
    mock_insert_errors.assert_awaited_once()


@pytest.mark.asyncio
async def test_insert_measurements_no_data(session):
    """Test early return when input is empty."""
    result = await insert_measurements(session, "asset123", [])
    assert result == {"status": "no data provided"}


@pytest.mark.asyncio
async def test_insert_measurements_upsert(session):
    """Test that duplicates upsert rather than fail."""
    ts = datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc)
    initial_rows = [{"timestamp": ts, "metric": "power", "value": 100.0}]
    updated_rows = [{"timestamp": ts, "metric": "power", "value": 101.0}]

    with patch(
        "app.measurement_service._insert_forecast_errors_for_new_measurements",
        new_callable=AsyncMock,
    ):
        result1 = await insert_measurements(session, "asset123", initial_rows)
        result2 = await insert_measurements(session, "asset123", updated_rows)

    assert result1["inserted"] == 1
    assert result2["inserted"] == 1


@pytest.mark.asyncio
async def test_insert_forecast_errors_returns_when_no_load_measurements(session):
    """If there are no load measurements, we should return early without DB calls."""
    measurements = [
        {"timestamp": datetime(2025, 10, 7, 12, 0), "metric": "temp", "value": 12.3},
        {"timestamp": datetime(2025, 10, 7, 13, 0), "metric": "power", "value": 99.0},
    ]

    await _insert_forecast_errors_for_new_measurements(session, "asset123", measurements)

    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


# -----------------------------
# _compute_forecast_errors tests
# -----------------------------


def test_compute_forecast_errors_basic():
    """Test pure function computes signed errors correctly."""
    forecasts = [
        {"timestamp": "2025-10-07T12:00:00Z", "forecast_run_id": 1, "forecast_value": 100},
        {"timestamp": "2025-10-07T13:00:00Z", "forecast_run_id": 1, "forecast_value": 105},
    ]
    measurements = [
        {"timestamp": "2025-10-07T12:00:00Z", "metric": "load", "value": 98},
        {"timestamp": "2025-10-07T13:00:00Z", "metric": "load", "value": 107},
    ]

    errors = _compute_forecast_errors(forecasts, measurements)
    assert len(errors) == 2
    assert errors[0]["error"] == 2
    assert errors[1]["error"] == -2
    assert all("forecast_run_id" in e for e in errors)
    assert all("timestamp" in e for e in errors)


# -----------------------------
# _insert_forecast_errors_for_new_measurements tests
# -----------------------------


@pytest.mark.asyncio
async def test_insert_forecast_errors_inserts_when_load_present(session):
    """Insert forecast errors when forecasts and load measurements exist."""
    # mock `await session.execute(q)` result for forecast lookup
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"timestamp": datetime(2025, 10, 7, 12, 0), "forecast_run_id": 1, "forecast_value": 100},
    ]
    session.execute.return_value = mock_result

    with patch("app.measurement_service._compute_forecast_errors") as mock_compute:
        mock_compute.return_value = [
            {"forecast_run_id": 1, "timestamp": datetime(2025, 10, 7, 12, 0), "error": 5}
        ]

        measurements = [{"timestamp": datetime(2025, 10, 7, 12, 0), "metric": "load", "value": 95}]
        await _insert_forecast_errors_for_new_measurements(session, "asset123", measurements)

    # We should have executed at least:
    # 1) forecast query
    # 2) insert stmt for errors (unless your implementation uses executemany etc.)
    assert session.execute.await_count >= 2
    session.commit.assert_awaited_once()
    mock_compute.assert_called_once()


@pytest.mark.asyncio
async def test_insert_forecast_errors_no_forecasts_found(session):
    """If no forecasts overlap timestamps, function returns early."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    session.execute.return_value = mock_result

    measurements = [{"timestamp": datetime(2025, 10, 7, 12, 0), "metric": "load", "value": 95}]

    await _insert_forecast_errors_for_new_measurements(session, "asset123", measurements)

    # only forecast query, no commits
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_insert_forecast_errors_no_matching_timestamps(session):
    """If forecasts exist but compute returns no errors, skip insert."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"timestamp": datetime(2025, 10, 7, 12, 0), "forecast_run_id": 1, "forecast_value": 100},
    ]
    session.execute.return_value = mock_result

    with patch("app.measurement_service._compute_forecast_errors", return_value=[]):
        measurements = [{"timestamp": datetime(2025, 10, 7, 12, 0), "metric": "load", "value": 95}]
        await _insert_forecast_errors_for_new_measurements(session, "asset123", measurements)

    session.commit.assert_not_awaited()
