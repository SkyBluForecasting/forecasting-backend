"""Unit tests for the constraint service module, including formatting and DB calls."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.constraint_service import format_constraints_rows, get_active_constraints


@pytest.mark.asyncio
async def test_get_active_constraints_formatting():
    """Test that format_constraints_rows correctly converts rows to API response."""
    mock_rows = [
        {
            "asset_uuid": "asset123",
            "forecast_uuid": UUID("11111111-1111-1111-1111-111111111111"),
            "start_time": datetime(2025, 9, 13, 21, 0, tzinfo=timezone.utc),
            "end_time": datetime(2025, 9, 13, 22, 0, tzinfo=timezone.utc),
            "constraint_kw": 38.081,
            "frequency_min": 60,
        },
        {
            "asset_uuid": "asset123",
            "forecast_uuid": UUID("11111111-1111-1111-1111-111111111111"),
            "start_time": datetime(2025, 9, 13, 22, 0, tzinfo=timezone.utc),
            "end_time": datetime(2025, 9, 13, 23, 0, tzinfo=timezone.utc),
            "constraint_kw": 819.49,
            "frequency_min": 60,
        },
    ]

    response = format_constraints_rows(mock_rows)

    assert "assets" in response
    assert len(response["assets"]) == 1

    asset = response["assets"][0]
    assert asset["asset_uuid"] == "asset123"
    assert asset["forecast_uuid"] == "11111111-1111-1111-1111-111111111111"
    assert asset["frequency_min"] == 60
    assert len(asset["constraints"]) == 2

    first_constraint = asset["constraints"][0]
    assert first_constraint["start_time"] == "2025-09-13T21:00:00Z"
    assert first_constraint["end_time"] == "2025-09-13T22:00:00Z"
    assert first_constraint["constraint_kw"] == 38.081


@pytest.mark.asyncio
async def test_get_active_constraints_calls_db():
    """Test get_active_constraints calls the database and formats the results correctly."""
    mock_rows = [
        {
            "asset_uuid": "asset123",
            "forecast_uuid": UUID("11111111-1111-1111-1111-111111111111"),
            "start_time": datetime(2025, 9, 13, 21, 0, tzinfo=timezone.utc),
            "end_time": datetime(2025, 9, 13, 22, 0, tzinfo=timezone.utc),
            "constraint_kw": 38.081,
            "frequency_min": 60,
        }
    ]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = mock_rows

    async_mock_session = AsyncMock()
    async_mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch(
        "app.constraint_service.AsyncSessionLocal", return_value=async_mock_session
    ):
        result = await get_active_constraints("asset123")

    assert "assets" in result
    asset = result["assets"][0]
    assert asset["asset_uuid"] == "asset123"
    assert asset["forecast_uuid"] == "11111111-1111-1111-1111-111111111111"
    assert len(asset["constraints"]) == 1
    constraint = asset["constraints"][0]
    assert constraint["start_time"] == "2025-09-13T21:00:00Z"
    assert constraint["end_time"] == "2025-09-13T22:00:00Z"
    assert constraint["constraint_kw"] == 38.081


@pytest.mark.asyncio
async def test_constraints_with_null_times():
    """Test format_constraints_rows handles rows with None start/end times correctly."""
    mock_rows = [
        {
            "asset_uuid": "asset123",
            "forecast_uuid": UUID("11111111-1111-1111-1111-111111111111"),
            "start_time": None,
            "end_time": None,
            "constraint_kw": 42.0,
            "frequency_min": 60,
        }
    ]

    response = format_constraints_rows(mock_rows)
    constraint = response["assets"][0]["constraints"][0]
    assert constraint["start_time"] is None
    assert constraint["end_time"] is None
    assert constraint["constraint_kw"] == 42.0


@pytest.mark.asyncio
async def test_constraints_multiple_assets():
    """Test format_constraints_rows correctly groups constraints for multiple assets."""
    mock_rows = [
        {
            "asset_uuid": "assetA",
            "forecast_uuid": UUID("11111111-1111-1111-1111-111111111111"),
            "start_time": datetime(2025, 9, 13, 21, 0, tzinfo=timezone.utc),
            "end_time": datetime(2025, 9, 13, 22, 0, tzinfo=timezone.utc),
            "constraint_kw": 50.0,
            "frequency_min": 60,
        },
        {
            "asset_uuid": "assetB",
            "forecast_uuid": UUID("22222222-2222-2222-2222-222222222222"),
            "start_time": datetime(2025, 9, 13, 21, 0, tzinfo=timezone.utc),
            "end_time": datetime(2025, 9, 13, 22, 0, tzinfo=timezone.utc),
            "constraint_kw": 75.0,
            "frequency_min": 30,
        },
    ]

    response = format_constraints_rows(mock_rows)
    assert len(response["assets"]) == 2
    uuids = {a["asset_uuid"] for a in response["assets"]}
    assert uuids == {"assetA", "assetB"}


@pytest.mark.asyncio
async def test_format_constraints_rows_empty():
    """Test format_constraints_rows returns empty assets list for empty input."""
    response = format_constraints_rows([])
    assert response == {"assets": []}
