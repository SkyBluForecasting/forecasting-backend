"""Unit tests for forecast_service.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.forecast_service import get_active_forecast, get_forecast_rows, get_recent_forecasts


@pytest.mark.asyncio
class TestGetActiveForecast:
    """Tests for get_active_forecast function."""

    async def test_returns_row(self):
        """Returns latest forecast_run as dict."""
        mock_row = {
            "forecast_run_id": "run111",
            "model_run_id": "model123",
            "asset_uuid": "asset123",
            "created_at": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            "start_time": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
            "end_time": datetime(2025, 10, 7, 13, 0, tzinfo=timezone.utc),
            "frequency_min": 60,
        }

        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = mock_row

        session = AsyncMock()
        session.execute.return_value = mock_result

        result = await get_active_forecast(session, "asset123")

        assert result["forecast_run_id"] == "run111"
        assert result["model_run_id"] == "model123"
        assert result["asset_uuid"] == "asset123"

    async def test_returns_none_if_no_row(self):
        """Returns None if no forecast_run exists."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None

        session = AsyncMock()
        session.execute.return_value = mock_result

        result = await get_active_forecast(session, "asset123")
        assert result is None


@pytest.mark.asyncio
class TestGetForecastRows:
    """Tests for get_forecast_rows function."""

    async def test_returns_rows(self):
        """Returns list of dicts with timestamp and forecast_kw."""
        mock_rows = [
            {
                "timestamp": datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc),
                "forecast_value": 100.0,
            },
            {
                "timestamp": datetime(2025, 10, 7, 13, 0, tzinfo=timezone.utc),
                "forecast_value": 105.5,
            },
        ]

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = mock_rows

        session = AsyncMock()
        session.execute.return_value = mock_result

        result = await get_forecast_rows(session, "run111")

        assert len(result) == 2
        assert result[0]["timestamp"].hour == 12
        assert result[0]["forecast_kw"] == 100.0
        assert result[1]["timestamp"].hour == 13
        assert result[1]["forecast_kw"] == 105.5

    async def test_returns_empty_list_if_no_rows(self):
        """Returns empty list if no forecast rows exist."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []

        session = AsyncMock()
        session.execute.return_value = mock_result

        result = await get_forecast_rows(session, "run111")
        assert result == []


@pytest.mark.asyncio
class TestGetRecentForecasts:
    """Tests for get_recent_forecasts function."""

    async def test_returns_last_two_forecasts(self):
        """Returns a list of the most recent forecasts up to the given limit."""
        mock_forecasts = [
            {"forecast_run_id": "run2", "model_run_id": "model2", "asset_uuid": "asset123"},
            {"forecast_run_id": "run1", "model_run_id": "model1", "asset_uuid": "asset123"},
        ]

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = mock_forecasts

        session = AsyncMock()
        session.execute.return_value = mock_result

        result = await get_recent_forecasts(session, "asset123", limit=2)

        assert len(result) == 2
        assert result[0]["forecast_run_id"] == "run2"
        assert result[1]["forecast_run_id"] == "run1"

    async def test_returns_empty_list_if_no_forecasts(self):
        """Returns empty list if no recent forecasts exist."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []

        session = AsyncMock()
        session.execute.return_value = mock_result

        result = await get_recent_forecasts(session, "asset123", limit=2)
        assert result == []
