"""Unit tests for forecast_service.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.forecast_service import (
    get_active_forecast,
    get_forecast_rows,
    get_latest_forecast,
    load_latest_forecast_data_from_s3,
    parse_forecast_csv,
)


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

        async_mock_session = AsyncMock()
        async_mock_session.__aenter__.return_value.execute.return_value = mock_result

        with patch("app.forecast_service.AsyncSessionLocal", return_value=async_mock_session):
            result = await get_active_forecast("asset123")

        assert result["forecast_run_id"] == "run111"
        assert result["model_run_id"] == "model123"
        assert result["asset_uuid"] == "asset123"

    async def test_returns_none_if_no_row(self):
        """Returns None if no forecast_run exists."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None

        async_mock_session = AsyncMock()
        async_mock_session.__aenter__.return_value.execute.return_value = mock_result

        with patch("app.forecast_service.AsyncSessionLocal", return_value=async_mock_session):
            result = await get_active_forecast("asset123")

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

        async_mock_session = AsyncMock()
        async_mock_session.__aenter__.return_value.execute.return_value = mock_result

        with patch("app.forecast_service.AsyncSessionLocal", return_value=async_mock_session):
            result = await get_forecast_rows("run111")

        assert len(result) == 2
        assert result[0]["timestamp"].hour == 12
        assert result[0]["forecast_kw"] == 100.0
        assert result[1]["timestamp"].hour == 13
        assert result[1]["forecast_kw"] == 105.5

    async def test_returns_empty_list_if_no_rows(self):
        """Returns empty list if no forecast rows exist."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []

        async_mock_session = AsyncMock()
        async_mock_session.__aenter__.return_value.execute.return_value = mock_result

        with patch("app.forecast_service.AsyncSessionLocal", return_value=async_mock_session):
            result = await get_forecast_rows("run111")

        assert result == []


class TestParseForecastCSV:
    """Unit tests for the parse_forecast_csv function."""

    def test_parses_valid_csv(self):
        """Parses a well-formed CSV string into a list of forecast dicts."""
        csv = "datetime,forecast\n2025-07-16T00:00:00+00:00,123.45\n"
        parsed = parse_forecast_csv(csv)

        assert parsed == [{"timestamp": "2025-07-16T00:00:00Z", "value_kw": 123.45}]

    def test_skips_rows_with_missing_fields(self, caplog):
        """Skips CSV rows with missing or invalid forecast data, logging a warning."""
        csv = "datetime,forecast\nmissing_value,\n"
        result = parse_forecast_csv(csv)

        assert result == []
        assert "Skipping row due to error" in caplog.text


class TestLoadLatestForecastDataFromS3:
    """Tests for loading the latest forecast CSV data from S3."""

    def test_returns_csv_string(self, mock_s3_with_forecast, set_s3_env):
        """Successfully fetches and returns CSV content as string from mocked S3."""
        with patch("app.forecast_service.get_s3_client", return_value=mock_s3_with_forecast), patch(
            "app.forecast_service.get_s3_bucket", return_value="my-test-bucket"
        ):

            content = load_latest_forecast_data_from_s3("test")
            assert "datetime" in content
            assert "123.45" in content

    def test_raises_if_no_forecasts_found(self, set_s3_env):
        """Raises HTTPException with 404 if no forecast files are found in S3."""
        empty_mock = MagicMock()
        empty_mock.list_objects_v2.return_value = {}

        with patch("app.forecast_service.get_s3_client", return_value=empty_mock), patch(
            "app.forecast_service.get_s3_bucket", return_value="my-test-bucket"
        ):

            with pytest.raises(HTTPException) as exc:
                load_latest_forecast_data_from_s3("test")

            assert exc.value.status_code == 404
            assert exc.value.detail == "No forecasts found"


class TestGetLatestForecast:
    """Tests for the get_latest_forecast service function."""

    def test_get_latest_forecast_success(self, mock_s3_with_forecast, set_s3_env):
        """Returns the correct structured forecast dict for a valid asset id."""
        with patch("app.forecast_service.get_s3_client", return_value=mock_s3_with_forecast), patch(
            "app.forecast_service.get_s3_bucket", return_value="my-test-bucket"
        ):

            result = get_latest_forecast("test")
            assert result["asset_id"] == "test"
            assert result["values"] == [{"timestamp": "2025-07-16T00:00:00Z", "value_kw": 123.45}]
