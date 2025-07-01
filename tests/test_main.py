"""Tests for the main FastAPI application."""

from unittest.mock import MagicMock, patch

import pytest
from authlib.jose import KeySet
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_latest_forecast():
    """Test the forecast endpoint with valid parameters."""
    # Create a mock key set
    mock_key_set = MagicMock(spec=KeySet)
    mock_key_set.find_by_kid.return_value = MagicMock()

    # Create mock claims
    mock_claims = MagicMock()
    mock_claims.get.side_effect = lambda key, default=None: {
        "sub": "test-subject",
        "scope": "read:forecast",
    }.get(key, default)
    mock_claims.validate = MagicMock()

    # Create mock S3 response
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: b'{"forecast": "test"}')
    }
    mock_s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "test/test/20240101.json"}]
    }

    # Patch BUCKET_NAME in app.s3
    with patch("app.s3.BUCKET_NAME", "dummy-bucket"), patch(
        "app.main.get_token", return_value="test-token"
    ), patch("app.auth.validate_token", return_value=mock_claims), patch(
        "app.auth.decode_jwt_header", return_value={"kid": "test-kid"}
    ), patch(
        "app.auth.get_cached_jwks", return_value=mock_key_set
    ), patch(
        "authlib.jose.jwt.decode", return_value=mock_claims
    ), patch(
        "app.s3.get_s3_client", return_value=mock_s3
    ):
        response = client.get(
            "/forecast/latest?asset_id=test",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"forecast": "test"}
