"""Authentication module for handling JWT token validation and Auth0 integration."""

import base64
import json
import logging
import os
from functools import lru_cache
from pathlib import Path

import requests
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError
from dotenv import load_dotenv
from fastapi import HTTPException, Request

# Make sure we point to the .env file explicitly
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path)

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
API_AUDIENCE = os.getenv("API_AUDIENCE")

if not AUTH0_DOMAIN or not API_AUDIENCE:
    raise RuntimeError(
        "Missing required Auth0 environment variables: "
        f"AUTH0_DOMAIN={AUTH0_DOMAIN}, API_AUDIENCE={API_AUDIENCE}"
    )

logger = logging.getLogger("auth")
ALGORITHMS = ["RS256"]

JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"


# --- Utility Functions ---
def decode_jwt_header(token: str) -> dict:
    """Decode the JWT header from a token.

    Args:
        token: The JWT token.

    Returns:
        dict: The decoded JWT header.

    Raises:
        HTTPException: If the header cannot be decoded.
    """
    try:
        header_b64 = token.split(".")[0]
        header_b64 += "=" * (-len(header_b64) % 4)  # Fix padding
        decoded_bytes = base64.urlsafe_b64decode(header_b64)
        return json.loads(decoded_bytes)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT header: {e}")


@lru_cache(maxsize=1)
def get_cached_jwks() -> JsonWebKey:
    """Get the cached JSON Web Key Set from Auth0.

    Returns:
        JsonWebKey: The cached JWKS.

    Raises:
        HTTPException: If the JWKS cannot be fetched.
    """
    try:
        logger.info("Fetching JWKS from Auth0")
        response = requests.get(JWKS_URL)
        response.raise_for_status()
        return JsonWebKey.import_key_set(response.json())
    except Exception as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch JWKS")


def get_key_id_from_token(token: str) -> str:
    """
    Extract the Key ID (kid) from the JWT token header.

    Args:
        token (str): The JWT token string.

    Raises:
        HTTPException: If the 'kid' is missing from the token header.

    Returns:
        str: The Key ID found in the token header.
    """
    header = decode_jwt_header(token)
    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Token missing 'kid' in header")
    return kid


def get_jwks_key(kid: str):
    """
    Retrieve the JSON Web Key (JWK) matching the given Key ID (kid).

    Attempts to get the key from a cached JWKS set and refreshes cache if needed.

    Args:
        kid (str): The Key ID to find in the JWKS.

    Raises:
        HTTPException: If no matching JWK is found.

    Returns:
        JWK: The matching JSON Web Key object.
    """
    try:
        key_set = get_cached_jwks()
        return key_set.find_by_kid(kid)
    except ValueError:
        # Cache might be stale, clear cache and try again
        get_cached_jwks.cache_clear()
        try:
            key_set = get_cached_jwks()
            return key_set.find_by_kid(kid)
        except ValueError:
            # Key still not found
            raise HTTPException(
                status_code=401, detail="Unable to find matching JWKS key"
            )


def decode_and_validate_claims(token: str, key) -> dict:
    """
    Decode the JWT token and validate its claims.

    Args:
        token (str): The JWT token string.
        key (JWK): The key to decode and validate the token.

    Returns:
        dict: The decoded and validated claims from the token.

    Raises:
        jwt.exceptions.InvalidTokenError: If token validation fails.
    """
    claims = jwt.decode(
        token,
        key,
        claims_options={
            "iss": {"essential": True, "value": f"https://{AUTH0_DOMAIN}/"},
            "aud": {"essential": True, "value": API_AUDIENCE},
            "exp": {"essential": True},
        },
    )
    claims.validate()
    return claims


def check_permissions(claims: dict):
    """
    Check if the JWT claims include the required permission 'read:forecast'.

    Args:
        claims (dict): The decoded JWT claims.

    Raises:
        HTTPException: If required permission 'read:forecast' is missing.
    """
    permissions = claims.get("permissions", [])
    if "read:forecast" not in permissions:
        scope = claims.get("scope", "")
        if "read:forecast" not in scope.split():
            raise HTTPException(
                status_code=403,
                detail="Token does not have required permission: read:forecast",
            )


def validate_token(token: str) -> dict:
    """Validate a JWT token.

    Args:
        token: The JWT token to validate.

    Returns:
        dict: The validated token claims.

    Raises:
        HTTPException: If the token is invalid or validation fails.
    """
    try:
        kid = get_key_id_from_token(token)
        logger.info(f"Token kid: {kid}")

        key = get_jwks_key(kid)
        logger.info("Using key to decode JWT")

        claims = decode_and_validate_claims(token, key)

        logger.info("Token claims: %s", claims)
        logger.info("Raw permissions: %s", claims.get("permissions"))
        logger.info("Raw scope: %s", claims.get("scope"))

        check_permissions(claims)

        logger.info(f"Token validated: subject={claims.get('sub')}")

        return claims

    except HTTPException:
        # Let FastAPI's own HTTP errors bubble up as-is
        raise
    except JoseError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token signature or claims")
    except Exception as e:
        logger.exception("Unexpected error during token validation")
        raise HTTPException(status_code=401, detail=str(e))


def get_token(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Not authenticated")
    return auth_header.split(" ")[1]
