"""Unit tests for forecast_service.py."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.forecast_service import (
    get_latest_forecast,
    load_latest_forecast_data_from_s3,
    parse_forecast_csv,
)


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
        with patch(
            "app.forecast_service.get_s3_client", return_value=mock_s3_with_forecast
        ), patch("app.forecast_service.get_s3_bucket", return_value="my-test-bucket"):

            content = load_latest_forecast_data_from_s3("test")
            assert "datetime" in content
            assert "123.45" in content

    def test_raises_if_no_forecasts_found(self, set_s3_env):
        """Raises HTTPException with 404 if no forecast files are found in S3."""
        empty_mock = MagicMock()
        empty_mock.list_objects_v2.return_value = {}

        with patch(
            "app.forecast_service.get_s3_client", return_value=empty_mock
        ), patch("app.forecast_service.get_s3_bucket", return_value="my-test-bucket"):

            with pytest.raises(HTTPException) as exc:
                load_latest_forecast_data_from_s3("test")

            assert exc.value.status_code == 404
            assert exc.value.detail == "No forecasts found"


class TestGetLatestForecast:
    """Tests for the get_latest_forecast service function."""

    def test_get_latest_forecast_success(self, mock_s3_with_forecast, set_s3_env):
        """Returns the correct structured forecast dict for a valid asset id."""
        with patch(
            "app.forecast_service.get_s3_client", return_value=mock_s3_with_forecast
        ), patch("app.forecast_service.get_s3_bucket", return_value="my-test-bucket"):

            result = get_latest_forecast("test")
            assert result["asset_id"] == "test"
            assert result["values"] == [
                {"timestamp": "2025-07-16T00:00:00Z", "value_kw": 123.45}
            ]
