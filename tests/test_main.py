"""Unit tests for FastAPI endpoints in app.main."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app


# -----------------------------
# Client fixture that triggers startup/shutdown
# -----------------------------
@pytest.fixture
def client():
    """Provide a TestClient that runs startup and shutdown events."""
    with TestClient(app) as c:
        yield c


# -----------------------------
# Automatically mock validate_token for all tests
# -----------------------------
@pytest.fixture(autouse=True)
def patch_validate_token():
    """Mock validate_token to always succeed."""
    with patch("app.main.validate_token", lambda token: True):
        yield


# -----------------------------
# Forecast endpoint tests
# -----------------------------
class TestReadLatestForecast:
    """Test cases for the /forecast/latest endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self):
        """Patch get_latest_forecast for all tests in this class."""
        with patch("app.main.get_latest_forecast", new_callable=MagicMock) as mock:
            self.mock_forecast_service = mock
            yield

    def test_successful_request(self, client):
        """Return 200 and forecast data for valid asset_id."""
        self.mock_forecast_service.return_value = {
            "asset_id": "test",
            "values": [{"timestamp": "2025-07-16T00:00:00Z", "value_kw": 123.45}],
        }

        response = client.get(
            "/forecast/latest?asset_id=test",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        assert response.json()["asset_id"] == "test"

    def test_non_existent_data_returns_404(self, client):
        """Return 404 when forecast data is not found."""
        self.mock_forecast_service.side_effect = HTTPException(
            status_code=404, detail="Forecast not found"
        )

        response = client.get(
            "/forecast/latest?asset_id=nonexistent",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 404


# -----------------------------
# Constraints endpoint tests
# -----------------------------
class TestReadActiveConstraints:
    """Test cases for the /constraints/active endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self):
        """Patch get_active_constraints for all tests in this class."""
        with patch("app.main.get_active_constraints", new_callable=AsyncMock) as mock:
            self.mock_constraint_service = mock
            yield

    def test_successful_request_with_asset_id(self, client):
        """Return 200 and constraint data when asset_id is provided."""
        self.mock_constraint_service.return_value = {
            "assets": [
                {
                    "asset_uuid": "asset123",
                    "forecast_uuid": "uuid123",
                    "frequency_min": 60,
                    "constraints": [
                        {
                            "start_time": "2024-01-01T12:00:00Z",
                            "end_time": "2024-01-01T12:15:00Z",
                            "constraint_kw": 100.5,
                        }
                    ],
                }
            ]
        }

        response = client.get(
            "/constraints/active?asset_uuid=asset123",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        assert response.json()["assets"][0]["asset_uuid"] == "asset123"

    def test_successful_request_without_asset_id(self, client):
        """Return 200 and empty list when no asset_id is provided."""
        self.mock_constraint_service.return_value = {"assets": []}

        response = client.get(
            "/constraints/active",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        assert response.json()["assets"] == []

    def test_database_error_returns_500(self, client):
        """Return 500 when database error occurs."""
        self.mock_constraint_service.side_effect = HTTPException(
            status_code=500, detail="Database error"
        )

        response = client.get(
            "/constraints/active",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 500
