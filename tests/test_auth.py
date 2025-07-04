"""Tests for the authentication module."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from authlib.jose import KeySet
from authlib.jose.errors import JoseError
from fastapi import HTTPException

from app.auth import (
    check_permissions,
    get_cached_jwks,
    get_jwks_key,
    get_key_id_from_token,
    validate_token,
)


class DummyKeySet:
    """Dummy JWKS key set for testing purposes."""

    def __init__(self, keys):
        """Initialize with a dict of keys."""
        self._keys = keys

    def find_by_kid(self, kid):
        """Return key matching the given kid or raise ValueError if not found."""
        if kid in self._keys:
            return self._keys[kid]
        else:
            raise ValueError("Invalid JSON Web Key Set")


def test_missing_env_vars_raises_runtime_error(mocker):
    """Test that missing Auth0 env vars raise a RuntimeError on import."""
    # Patch environment to remove the required vars
    mocker.patch.dict(
        os.environ, {"AUTH0_DOMAIN": "", "AUTH0_AUDIENCE": ""}, clear=True
    )

    # Remove the module from sys.modules so it reloads from scratch
    if "app.auth" in sys.modules:
        del sys.modules["app.auth"]

    with pytest.raises(RuntimeError) as exc_info:
        import app.auth  # this will re-run the module top-level code

    assert "Missing required Auth0 environment variables" in str(exc_info.value)


class TestGetKidFromToken:
    """Tests for get_key_id_from_token function."""

    def test_get_kid_from_token_success(self, mocker):
        """Test extraction of 'kid' from token header succeeds."""
        mocker.patch("app.auth.decode_jwt_header", return_value={"kid": "abc123"})
        kid = get_key_id_from_token("fake.token")
        assert kid == "abc123"

    def test_get_kid_from_token_missing_kid(self, mocker):
        """Test HTTPException raised if 'kid' is missing in token header."""
        mocker.patch("app.auth.decode_jwt_header", return_value={})
        with pytest.raises(HTTPException) as exc_info:
            get_key_id_from_token("fake.token")
        assert exc_info.value.status_code == 401
        assert "missing 'kid'" in exc_info.value.detail


class TestGetJWKSKey:
    """Tests for get_jwks_key function."""

    def test_get_cached_jwks_key(self, mocker):
        """Test returning key from cached JWKS."""
        key = {"key": "testkey"}
        key_set = DummyKeySet({"abc123": key})

        mocker.patch("app.auth.get_cached_jwks", return_value=key_set)
        result = get_jwks_key("abc123")
        assert result == key

    def test_get_jwks_key_not_found(self, mocker):
        """Test HTTPException if JWKS key not found after cache refresh."""
        # Two separate empty KeySet instances
        empty_key_set1 = KeySet(keys=[])
        empty_key_set2 = KeySet(keys=[])

        mocker.patch(
            "app.auth.get_cached_jwks",
            side_effect=[empty_key_set1, empty_key_set2],  # different instances
        )

        mocker.patch("app.auth.get_cached_jwks.cache_clear", lambda: None)

        with pytest.raises(HTTPException) as exc_info:
            get_jwks_key("abc123")

        assert exc_info.value.status_code == 401
        assert "Unable to find matching JWKS key" in exc_info.value.detail

    def test_get_jwks_key_cache_miss_then_refresh(self, mocker):
        """Test cache miss followed by refresh returns correct key."""
        key = {"key": "refreshedkey"}
        first_key_set = DummyKeySet({})
        refreshed_key_set = DummyKeySet({"abc123": key})

        mock_get_cached_jwks = mocker.patch(
            "app.auth.get_cached_jwks", side_effect=[first_key_set, refreshed_key_set]
        )
        mocker.patch("app.auth.get_cached_jwks.cache_clear")

        result = get_jwks_key("abc123")
        assert result == key
        assert mock_get_cached_jwks.call_count == 2

    def test_get_cached_jwks_fetches_when_cache_empty(self, mocker):
        """Test JWKS fetch when cache is empty."""
        get_cached_jwks.cache_clear()  # force fetch

        # Simulate Auth0 returning an empty key set
        mock_response = mocker.Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"keys": []}

        mocker.patch("app.auth.requests.get", return_value=mock_response)
        mock_import = mocker.patch("app.auth.JsonWebKey.import_key_set")

        get_cached_jwks()

        mock_import.assert_called_once_with({"keys": []})

    def test_get_cached_jwks_raises_on_fetch_failure(self, mocker):
        """Test HTTPException on JWKS fetch failure."""
        # Clear any cache so the function runs
        get_cached_jwks.cache_clear()

        # Patch the actual call inside the function
        mocker.patch(
            "app.auth.requests.get", side_effect=Exception("Simulated network error")
        )

        with pytest.raises(HTTPException) as exc_info:
            get_cached_jwks()

        assert exc_info.value.status_code == 500
        assert "Unable to fetch JWKS" in exc_info.value.detail


class TestPermissions:
    """Tests for the check_permissions function."""

    def test_check_permissions_with_permission(self):
        """Should pass when 'read:forecast' permission is present."""
        claims = {"permissions": ["read:forecast"]}
        check_permissions(claims)  # should not raise

    def test_check_permissions_with_scope(self):
        """Should pass when 'read:forecast' is in the scope string."""
        claims = {"permissions": [], "scope": "read:forecast write:something"}
        check_permissions(claims)  # should not raise

    def test_check_permissions_fails(self):
        """Should raise HTTPException if required permission is missing."""
        claims = {"permissions": [], "scope": "write:something"}

        with pytest.raises(HTTPException) as exc_info:
            check_permissions(claims)

        assert exc_info.value.status_code == 403
        assert "required permission" in exc_info.value.detail


class TestValidateToken:
    """Tests for the validate_token function."""

    def test_valid_token(self, mocker):
        """Should return claims when token is valid."""
        mocker.patch("app.auth.get_key_id_from_token", return_value="abc123")
        mocker.patch("app.auth.get_jwks_key", return_value="fake-key")
        mocker.patch(
            "app.auth.decode_and_validate_claims",
            return_value={"sub": "user123", "permissions": ["read:forecast"]},
        )
        mocker.patch("app.auth.check_permissions")

        result = validate_token("fake-token")

        assert result["sub"] == "user123"

    def test_missing_key_id_raises_401(self, mocker):
        """Should raise 401 if 'kid' is missing in the token."""
        mocker.patch(
            "app.auth.get_key_id_from_token",
            side_effect=HTTPException(status_code=401, detail="Token missing 'kid'"),
        )
        with pytest.raises(HTTPException) as exc:
            validate_token("bad-token")
        assert exc.value.status_code == 401
        assert "missing 'kid" in exc.value.detail

    def test_jwks_key_not_found_raises_401(self, mocker):
        """Should raise 401 if JWKS key cannot be found."""
        mocker.patch("app.auth.get_key_id_from_token", return_value="abc123")
        mocker.patch(
            "app.auth.get_jwks_key",
            side_effect=HTTPException(
                status_code=401, detail="Unable to find matching JWKS key"
            ),
        )
        with pytest.raises(HTTPException) as exc:
            validate_token("bad-token")
        assert exc.value.status_code == 401
        assert "matching JWKS key" in exc.value.detail

    def test_decode_jwt_raises_joseerror(self, mocker):
        """Should raise 401 if token signature is invalid."""
        mocker.patch("app.auth.get_key_id_from_token", return_value="abc123")
        mocker.patch("app.auth.get_jwks_key", return_value="fake-key")
        mocker.patch(
            "app.auth.decode_and_validate_claims",
            side_effect=JoseError("bad signature"),
        )
        with pytest.raises(HTTPException) as exc:
            validate_token("bad-token")
        assert exc.value.status_code == 401
        assert "Invalid token signature" in exc.value.detail

    def test_missing_permission_raises_403(self, mocker):
        """Should raise 403 if token lacks required permissions."""
        mocker.patch("app.auth.get_key_id_from_token", return_value="abc123")
        mocker.patch("app.auth.get_jwks_key", return_value="fake-key")
        mocker.patch(
            "app.auth.decode_and_validate_claims",
            return_value={"sub": "user123", "permissions": []},
        )
        mocker.patch(
            "app.auth.check_permissions",
            side_effect=HTTPException(
                status_code=403,
                detail="Token does not have required permission: read:forecast",
            ),
        )

        with pytest.raises(HTTPException) as exc:
            validate_token("fake-token")
        assert exc.value.status_code == 403

    def test_unexpected_exception(self, mocker):
        """Should raise 401 for unexpected exceptions during validation."""
        mocker.patch(
            "app.auth.get_key_id_from_token", side_effect=Exception("Unexpected!")
        )
        with pytest.raises(HTTPException) as exc:
            validate_token("some-token")
        assert exc.value.status_code == 401
        assert "Unexpected" in exc.value.detail
