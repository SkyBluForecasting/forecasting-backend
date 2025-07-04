"""Tests for the main FastAPI application."""

from unittest.mock import MagicMock, patch

import pytest
from authlib.jose import KeySet
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_dependencies():
    """
    Fixture to mock external dependencies for FastAPI tests.

    This includes mocking:
    - Auth token extraction
    - Token validation and decoding
    - JWKS key fetching
    - S3 client methods (get_object, list_objects_v2)

    The mocks ensure tests run isolated from external services.
    """
    mock_key_set = MagicMock(spec=KeySet)
    mock_key_set.find_by_kid.return_value = MagicMock()

    mock_claims = MagicMock()
    mock_claims.get.side_effect = lambda key, default=None: {
        "sub": "test-subject",
        "scope": "read:forecast",
    }.get(key, default)
    mock_claims.validate = MagicMock()

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: b'{"forecast": "test"}')
    }
    mock_s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "test/test/20240101.json"}]
    }

    patches = [
        patch("app.main.get_token", return_value="test-token"),
        patch("app.auth.validate_token", return_value=mock_claims),
        patch("app.auth.decode_jwt_header", return_value={"kid": "test-kid"}),
        patch("app.auth.get_cached_jwks", return_value=mock_key_set),
        patch("authlib.jose.jwt.decode", return_value=mock_claims),
        patch("app.s3.get_s3_client", return_value=mock_s3),
    ]

    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


class TestReadLatestForecast:
    """Tests for the /forecast/latest endpoint."""

    def test_successful_request(self, mock_dependencies):
        """Returns 200 and forecast data on valid request with authentication."""
        response = client.get(
            "/forecast/latest?utility_id=test&asset_id=test",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"forecast": "test"}

    def test_missing_header_returns_403(self, mock_dependencies):
        """Returns 403 if Authorization header is missing."""
        response = client.get("/forecast/latest?utility_id=test&asset_id=test")
        assert response.status_code == 403
        assert response.json() == {"detail": "Not authenticated"}

    def test_invalid_token_returns_401(self):
        """Returns 401 for invalid JWT token."""
        invalid_token = "Bearer this.is.not.a.valid.token"
        response = client.get(
            "/forecast/latest?asset_id=test", headers={"Authorization": invalid_token}
        )

        assert response.status_code == 401
        assert "Invalid JWT" in response.json()["detail"]

    def test_non_existent_data_returns_404(self, mock_dependencies):
        """Returns 404 if forecast data does not exist."""
        asset_id = "nonexistent-asset"

        with patch("app.main.get_latest_forecast") as mock_get_forecast:
            mock_get_forecast.side_effect = HTTPException(
                status_code=404, detail="Forecast not found"
            )

            response = client.get(
                f"/forecast/latest?asset_id={asset_id}",
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Forecast not found"}

    def test_missing_required_params_returns_422(self, mock_dependencies):
        """Returns 422 if required query parameters are missing."""
        response = client.get(
            "/forecast/latest",  # no asset_id query parameter
            headers={"Authorization": "Bearer test-token"},
        )
        print(response.json())
        assert response.status_code == 422
        # Optionally, check error detail includes asset_id is missing
        assert any(
            err["loc"] == ["query", "asset_id"] and err["type"] == "missing"
            for err in response.json()["detail"]
        )
