"""Unit tests for FastAPI endpoints in app.main."""

from unittest.mock import AsyncMock, patch

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
    """Mock validate_token to always succeed for all tests."""
    with patch("app.main.validate_token", lambda token: True):
        yield


# -----------------------------
# Helper fixture for patching async services
# -----------------------------
@pytest.fixture
def patch_service():
    """Return a helper to patch async service functions.

    Usage:
        mock_service = patch_service("app.main.some_async_function")
        mock_service.return_value = ...
    """
    patches = []

    def _patch(target):
        mock = AsyncMock()
        p = patch(target, new=mock)
        p.start()
        patches.append(p)
        return mock

    yield _patch

    for p in patches:
        p.stop()


# -----------------------------
# Constraints endpoint tests
# -----------------------------
class TestGetActiveConstraints:
    """Tests for the GET /constraints/active endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self, patch_service):
        """Automatically patch the get_active_constraints service."""
        self.mock_constraint_service = patch_service("app.main.get_active_constraints")

    def test_successful_request_with_asset_id(self, client):
        """Returns the correct subtree when an asset UUID is provided."""
        self.mock_constraint_service.return_value = {
            "assets": [
                {
                    "asset_uuid": "asset123",
                    "forecast_uuid": "11111111-1111-1111-1111-111111111111",
                    "forecast_run_id": "run123",
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

        resp = client.get(
            "/constraints/active?asset_uuid=asset123",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["assets"][0]["asset_uuid"] == "asset123"

    def test_successful_request_without_asset_id(self, client):
        """Returns all assets when no asset UUID is provided."""
        self.mock_constraint_service.return_value = {"assets": []}

        resp = client.get("/constraints/active", headers={"Authorization": "Bearer fake-token"})
        assert resp.status_code == 200
        assert resp.json()["assets"] == []

    def test_database_error_returns_500(self, client):
        """Handles database errors and returns 500 status."""
        self.mock_constraint_service.side_effect = HTTPException(
            status_code=500, detail="Database error"
        )
        resp = client.get("/constraints/active", headers={"Authorization": "Bearer fake-token"})
        assert resp.status_code == 500


# -----------------------------
# Dashboard endpoint tests
# -----------------------------
class TestGetDashboardAssetData:
    """Tests for the GET /dashboard/assets/{asset_uuid}/data endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self, patch_service):
        """Automatically patch the get_dashboard_asset_data service."""
        self.mock_dashboard_service = patch_service("app.main.get_dashboard_asset_data")

    def test_no_forecast_returns_empty_lists(self, client):
        """Returns empty lists when no forecasts exist for an asset."""
        self.mock_dashboard_service.return_value = {
            "asset_uuid": "asset123",
            "latest_forecasts": [],
            "previous_forecasts": [],
            "measurements": {"metrics": [], "values": [], "units": {"load": "kW", "temp": "C"}},
        }

        resp = client.get(
            "/dashboard/assets/asset123/data", headers={"Authorization": "Bearer fake-token"}
        )
        data = resp.json()
        assert data["latest_forecasts"] == []
        assert data["previous_forecasts"] == []
        assert data["measurements"]["metrics"] == []
        assert data["measurements"]["units"]["load"] == "kW"

    def test_forecasts_with_accuracy_metrics(self, client):
        """Returns forecasts including accuracy metrics and measurements."""
        latest_forecast = {
            "forecast_run_id": "run111",
            "model_run_id": "model123",
            "values": [
                {"timestamp": "2025-09-13T21:00:00Z", "forecast_kw": 50},
                {"timestamp": "2025-09-13T22:00:00Z", "forecast_kw": 55},
            ],
            "accuracy_metrics": {"mae": 1.5, "mape": 0.0285},
        }
        previous_forecast = {
            "forecast_run_id": "run110",
            "model_run_id": "model122",
            "values": [
                {"timestamp": "2025-09-12T21:00:00Z", "forecast_kw": 40},
                {"timestamp": "2025-09-12T22:00:00Z", "forecast_kw": 45},
            ],
            "accuracy_metrics": {"mae": 1.0, "mape": 0.0237},
        }
        measurements = {
            "metrics": ["load", "temp"],
            "values": [
                {"timestamp": "2025-09-13T21:00:00Z", "values": {"load": 100, "temp": 25}},
                {"timestamp": "2025-09-13T22:00:00Z", "values": {"load": 101, "temp": 26}},
            ],
            "units": {"load": "kW", "temp": "C"},
        }

        self.mock_dashboard_service.return_value = {
            "asset_uuid": "asset123",
            "latest_forecasts": [latest_forecast],
            "previous_forecasts": [previous_forecast],
            "measurements": measurements,
        }

        resp = client.get(
            "/dashboard/assets/asset123/data", headers={"Authorization": "Bearer fake-token"}
        )
        data = resp.json()
        # Forecasts
        assert data["latest_forecasts"][0]["forecast_run_id"] == "run111"
        assert data["previous_forecasts"][0]["forecast_run_id"] == "run110"
        # Accuracy metrics
        assert data["latest_forecasts"][0]["accuracy_metrics"]["mae"] == 1.5
        assert data["previous_forecasts"][0]["accuracy_metrics"]["mae"] == 1.0
        assert data["latest_forecasts"][0]["accuracy_metrics"]["mape"] == pytest.approx(0.0285)
        assert data["previous_forecasts"][0]["accuracy_metrics"]["mape"] == pytest.approx(0.0237)
        # Measurements
        meas = data["measurements"]
        assert meas["metrics"] == ["load", "temp"]
        assert meas["units"]["load"] == "kW"
        assert meas["units"]["temp"] == "C"


# -----------------------------
# Measurements POST endpoint tests
# -----------------------------
class TestPostMeasurements:
    """Tests for the POST /assets/{asset_uuid}/measurements/ endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self, patch_service):
        """Automatically patch the insert_measurements service."""
        self.mock_insert_service = patch_service("app.main.insert_measurements")

    def test_successful_insert(self, client):
        """Inserts measurements successfully and returns count."""
        self.mock_insert_service.return_value = None
        payload = {
            "measurements": [
                {"timestamp": "2025-09-13T21:00:00Z", "metric": "load", "value": 100},
                {"timestamp": "2025-09-13T22:00:00Z", "metric": "temp", "value": 110},
            ]
        }

        resp = client.post(
            "/assets/asset123/measurements/",
            json=payload,
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "asset_uuid": "asset123",
            "inserted_count": 2,
            "message": "Measurements inserted successfully",
        }

    def test_empty_measurements_returns_no_data(self, client):
        """Handles empty measurement payload gracefully."""
        self.mock_insert_service.return_value = None
        resp = client.post(
            "/assets/asset123/measurements/",
            json={"measurements": []},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["inserted_count"] == 0

    def test_database_error_returns_500(self, client):
        """Handles database errors and returns 500 status."""
        self.mock_insert_service.side_effect = HTTPException(500, "Database error")
        payload = {
            "measurements": [{"timestamp": "2025-09-13T21:00:00Z", "metric": "load", "value": 100}]
        }
        resp = client.post(
            "/assets/asset123/measurements/",
            json=payload,
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 500


# -----------------------------
# Measurements GET endpoint tests
# -----------------------------
class TestGetMeasurements:
    """Tests for the GET /assets/{asset_uuid}/measurements/ endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self, patch_service):
        """Automatically patch the get_all_measurements service."""
        self.mock_get_measurements = patch_service("app.main.get_all_measurements")

    def test_successful_get_measurements(self, client):
        """Returns all measurements for a given time range successfully."""
        self.mock_get_measurements.return_value = {
            "metrics": ["load"],
            "values": [
                {"timestamp": "2025-09-13T21:00:00Z", "values": {"load": 100}},
                {"timestamp": "2025-09-13T22:00:00Z", "values": {"load": 110}},
            ],
            "units": {"load": "kW"},
        }
        resp = client.get(
            "/assets/asset123/measurements/",
            params={"start_time": "2025-09-13T21:00:00", "end_time": "2025-09-13T22:00:00"},
            headers={"Authorization": "Bearer fake-token"},
        )
        data = resp.json()
        assert resp.status_code == 200
        assert data["metrics"] == ["load"]
        assert len(data["values"]) == 2

    def test_invalid_datetime_returns_400(self, client):
        """Returns 400 for invalid datetime parameters."""
        resp = client.get(
            "/assets/asset123/measurements/?start_time=not-a-date&end_time=2025-09-13T22:00:00",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 400
        assert "Invalid datetime format" in resp.text


# -----------------------------
# Assets POST endpoint tests
# -----------------------------
class TestPostAssets:
    """Tests for the POST /assets endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self, patch_service):
        """Automatically patch the upsert_assets service."""
        self.mock_upsert_assets = patch_service("app.main.upsert_assets")

    def test_successful_post_assets(self, client):
        """Successfully inserts nested assets."""
        self.mock_upsert_assets.return_value = {"inserted": 2, "updated": 0, "total": 2}
        payload = [
            {
                "id": "ontario",
                "name": "Ontario",
                "type": "system",
                "capacity_kw": 80000.0,
                "measured": False,
                "assets": [
                    {
                        "id": "K0B",
                        "name": "K0B",
                        "type": "distribution_substation",
                        "capacity_kw": 70000.0,
                        "assets": [],
                        "measured": True,
                    }
                ],
            }
        ]
        resp = client.post("/assets", json=payload, headers={"Authorization": "Bearer fake-token"})
        assert resp.status_code == 200
        assert resp.json() == {"inserted": 2, "updated": 0, "total": 2}
        self.mock_upsert_assets.assert_awaited_once()

    def test_invalid_payload_returns_422(self, client):
        """Returns 422 for invalid asset payloads."""
        resp = client.post(
            "/assets",
            json=[{"name": "BadAsset", "type": "substation"}],
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 422


# -----------------------------
# Assets GET endpoint tests
# -----------------------------
class TestGetAssets:
    """Tests for the GET /assets endpoint."""

    @pytest.fixture(autouse=True)
    def _setup_mock(self, patch_service):
        """Automatically patch the fetch_assets service."""
        self.mock_fetch_assets = patch_service("app.main.fetch_assets")

    def test_get_all_assets_success(self, client):
        """Returns all assets in hierarchical tree structure."""
        self.mock_fetch_assets.return_value = [
            {
                "asset_uuid": "ONT",
                "name": "Ontario",
                "asset_type": "system",
                "capacity_kw": 0,
                "parent_uuid": None,
                "depth": 0,
                "measured": False,
                "children": [
                    {
                        "asset_uuid": "K0A",
                        "name": "K0A",
                        "asset_type": "distribution_substation",
                        "capacity_kw": 80000.0,
                        "parent_uuid": "ONT",
                        "depth": 1,
                        "measured": False,
                        "children": [],
                    },
                    {
                        "asset_uuid": "K0B",
                        "name": "K0B",
                        "asset_type": "distribution_substation",
                        "capacity_kw": 70000.0,
                        "parent_uuid": "ONT",
                        "depth": 1,
                        "measured": True,
                        "children": [],
                    },
                ],
            }
        ]

        resp = client.get("/assets", headers={"Authorization": "Bearer fake-token"})
        data = resp.json()
        assert resp.status_code == 200
        assert len(data) == 1
        root = data[0]
        assert root["asset_uuid"] == "ONT"
        assert {c["asset_uuid"] for c in root["children"]} == {"K0A", "K0B"}
        self.mock_fetch_assets.assert_awaited_once()

    def test_get_single_asset_success(self, client):
        """Returns a single asset and its children (if any)."""
        self.mock_fetch_assets.return_value = [
            {
                "asset_uuid": "XYZ1",
                "name": "Sub A",
                "asset_type": "distribution_substation",
                "capacity_kw": 50000.0,
                "parent_uuid": None,
                "depth": 0,
                "measured": False,
                "children": [],
            }
        ]

        resp = client.get("/assets?asset_uuid=XYZ1", headers={"Authorization": "Bearer fake-token"})
        data = resp.json()
        assert resp.status_code == 200
        assert len(data) == 1
        assert data[0]["asset_uuid"] == "XYZ1"
        assert data[0]["children"] == []
        self.mock_fetch_assets.assert_awaited_once()
