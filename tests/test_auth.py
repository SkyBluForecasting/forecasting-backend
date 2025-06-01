"""Tests for the authentication module."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth import validate_token


def test_validate_token():
    """Test token validation with a valid token."""
    # Create a mock claims object with a validate method
    mock_claims = MagicMock()
    mock_claims.get.side_effect = lambda key, default=None: {
        "sub": "test-subject",
        "scope": "read:forecast",
    }.get(key, default)
    mock_claims.validate = MagicMock()

    # Mock the token validation to return our mock claims
    with patch("app.auth.get_cached_jwks"), patch(
        "app.auth.decode_jwt_header", return_value={"kid": "test-kid"}
    ), patch("authlib.jose.jwt.decode", return_value=mock_claims):
        result = validate_token("test.token")
        assert result == mock_claims
