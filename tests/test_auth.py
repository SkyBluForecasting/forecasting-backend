import pytest
from fastapi import HTTPException
from app.auth import validate_token
from unittest.mock import patch, MagicMock

def test_validate_token():
    # Create a mock claims object with a validate method
    mock_claims = MagicMock()
    mock_claims.get.return_value = "test-subject"
    
    # Mock the token validation to return our mock claims
    with patch("app.auth.get_cached_jwks"), \
         patch("app.auth.decode_jwt_header", return_value={"kid": "test-kid"}), \
         patch("authlib.jose.jwt.decode", return_value=mock_claims):
        result = validate_token("test.token")
        assert result == mock_claims
