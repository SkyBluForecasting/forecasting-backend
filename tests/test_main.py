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
                    "forecast_uuid": "11111111-1111-1111-1111-111111111111",
                    "forecast_run_id": "run123",  # <-- added
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


# -----------------------------
# Dashboard endpoint tests
# -----------------------------
class TestReadDashboardAssetData:
    """Test cases for the /dashboard/assets/{asset_uuid}/data/active endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self):
        """Patch get_dashboard_asset_data for all tests in this class."""
        with patch("app.main.get_dashboard_asset_data", new_callable=AsyncMock) as mock:
            self.mock_dashboard_service = mock
            yield

    def test_no_forecast_returns_none(self, client):
        """Return 200 with None forecast and measurements when no active forecast."""
        asset_uuid = "asset123"
        self.mock_dashboard_service.return_value = {
            "asset_uuid": asset_uuid,
            "forecast": None,
            "measurements": None,
        }

        response = client.get(
            f"/dashboard/assets/{asset_uuid}/data/active",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["asset_uuid"] == asset_uuid
        assert data["forecast"] is None
        assert data["measurements"] is None

    def test_returns_forecast_and_measurements(self, client):
        """Return 200 with forecast values and measurements."""
        asset_uuid = "asset123"
        forecast_uuid = "11111111-1111-1111-1111-111111111111"
        run_uuid = "run123"

        forecast_values = [
            {"timestamp": "2025-09-13T21:00:00Z", "forecast_kw": 50},
            {"timestamp": "2025-09-13T22:00:00Z", "forecast_kw": 55},
        ]

        measurements = {
            "metrics": ["metric1"],
            "values": [
                {"timestamp": "2025-09-13T21:00:00Z", "metric1": 100},
                {"timestamp": "2025-09-13T22:00:00Z", "metric1": 110},
            ],
        }

        self.mock_dashboard_service.return_value = {
            "asset_uuid": asset_uuid,
            "forecast": {
                "forecast_uuid": forecast_uuid,
                "forecast_run_id": run_uuid,  # <-- updated to match Pydantic schema
                "values": forecast_values,
            },
            "measurements": measurements,
        }

        response = client.get(
            f"/dashboard/assets/{asset_uuid}/data/active",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["asset_uuid"] == asset_uuid
        assert data["forecast"]["forecast_uuid"] == forecast_uuid
        assert data["forecast"]["forecast_run_id"] == run_uuid
        assert data["forecast"]["values"] == forecast_values
        assert data["measurements"] == measurements

    def test_invalid_asset_uuid_returns_404(self, client):
        """Return 404 when dashboard data not found."""
        asset_uuid = "invalid-asset"
        self.mock_dashboard_service.side_effect = HTTPException(
            status_code=404, detail="Dashboard data not found"
        )

        response = client.get(
            f"/dashboard/assets/{asset_uuid}/data/active",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 404


# -----------------------------
# Measurements POST endpoint tests
# -----------------------------
class TestPostMeasurements:
    """Test cases for the /assets/{asset_uuid}/measurements POST endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self):
        """Patch insert_measurements for all tests in this class."""
        with patch("app.main.insert_measurements", new_callable=AsyncMock) as mock:
            self.mock_insert_service = mock
            yield

    def test_successful_insert(self, client):
        """Return 200 when measurements are successfully inserted."""
        self.mock_insert_service.return_value = {"status": "success", "inserted": 2}

        payload = {
            "measurements": [
                {"timestamp": "2025-09-13T21:00:00Z", "metric": "load", "value": 100},
                {"timestamp": "2025-09-13T22:00:00Z", "metric": "temp", "value": 110},
            ]
        }

        response = client.post(
            "/assets/asset123/measurements",
            json=payload,
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "success", "inserted": 2}

    def test_empty_measurements_returns_no_data(self, client):
        """Return 200 with no data message if measurements list is empty."""
        self.mock_insert_service.return_value = {"status": "no data provided"}

        payload = {"measurements": []}

        response = client.post(
            "/assets/asset123/measurements",
            json=payload,
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "no data provided"}

    def test_database_error_returns_500(self, client):
        """Return 500 when database insert fails."""
        self.mock_insert_service.side_effect = HTTPException(
            status_code=500, detail="Database error"
        )

        payload = {
            "measurements": [{"timestamp": "2025-09-13T21:00:00Z", "metric": "load", "value": 100}]
        }

        response = client.post(
            "/assets/asset123/measurements",
            json=payload,
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 500


# -----------------------------
# Measurements GET endpoint tests
# -----------------------------
class TestGetMeasurements:
    """Test cases for the /assets/{asset_uuid}/measurements GET endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self):
        """Patch get_all_measurements for all tests in this class."""
        with patch("app.main.get_all_measurements", new_callable=AsyncMock) as mock:
            self.mock_get_measurements = mock
            yield

    def test_successful_get_measurements(self, client):
        """Return 200 and measurement data for valid params."""
        self.mock_get_measurements.return_value = {
            "metrics": ["load"],
            "values": [
                {"timestamp": "2025-09-13T21:00:00Z", "values": {"load": 100}},
                {"timestamp": "2025-09-13T22:00:00Z", "values": {"load": 110}},
            ],
        }

        response = client.get(
            "/assets/asset123/measurements/",
            params={
                "start_time": "2025-09-13T21:00:00",
                "end_time": "2025-09-13T22:00:00",
            },
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metrics"] == ["load"]
        assert len(data["values"]) == 2

    def test_invalid_datetime_returns_400(self, client):
        """Return 400 if datetime format is invalid."""
        response = client.get(
            "/assets/asset123/measurements/?start_time=not-a-date&end_time=2025-09-13T22:00:00",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 400
        assert "Invalid datetime format" in response.text
