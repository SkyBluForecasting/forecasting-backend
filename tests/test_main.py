import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, MagicMock
from authlib.jose import KeySet

client = TestClient(app)

def test_read_forecast():
    # Create a mock key set
    mock_key_set = MagicMock(spec=KeySet)
    mock_key_set.find_by_kid.return_value = MagicMock()
    
    # Create mock claims
    mock_claims = MagicMock()
    mock_claims.get.return_value = "test-subject"
    
    # Create mock S3 response
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: b'{"forecast": "test"}')
    }
    
    # Mock the token validation and S3 functions
    with patch("app.main.get_token", return_value="test-token"), \
         patch("app.auth.validate_token", return_value=mock_claims), \
         patch("app.auth.decode_jwt_header", return_value={"kid": "test-kid"}), \
         patch("app.auth.get_cached_jwks", return_value=mock_key_set), \
         patch("authlib.jose.jwt.decode", return_value=mock_claims), \
         patch("app.s3.get_s3_client", return_value=mock_s3):
        response = client.get(
            "/forecast?utility_id=test&asset_id=test&date=2024-03-24",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200
        assert response.json() == {"forecast": "test"}
