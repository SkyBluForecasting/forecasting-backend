"""Authentication module for handling JWT token validation and Auth0 integration."""

import base64
import json
import logging
from functools import lru_cache

import requests
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError
from fastapi import HTTPException

# --- Configuration ---
AUTH0_DOMAIN = "dev-zk4j1lb7dnrwc0xg.us.auth0.com"
API_AUDIENCE = "https://forecasting-api.forecasting"
ALGORITHMS = ["RS256"]
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"

logger = logging.getLogger("auth")


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
        header = decode_jwt_header(token)
        kid = header.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Token missing 'kid' in header")

        logger.info(f"Token kid: {kid}")

        # Attempt to find key from cached JWKS
        key_set = get_cached_jwks()
        key = key_set.find_by_kid(kid)

        # If no key found, force refresh JWKS
        if not key:
            logger.warning("Key not found in cache — refreshing JWKS")
            get_cached_jwks.cache_clear()
            key_set = get_cached_jwks()
            key = key_set.find_by_kid(kid)
            if not key:
                raise HTTPException(
                    status_code=401, detail="Unable to find matching JWKS key"
                )

        logger.info("Using key to decode JWT")

        # Decode and validate claims
        claims = jwt.decode(
            token,
            key,
            claims_options={
                "iss": {"essential": True, "value": f"https://{AUTH0_DOMAIN}/"},
                "aud": {"essential": True, "value": API_AUDIENCE},
                "exp": {"essential": True},
            },
        )
        claims.validate()  # checks exp, nbf, etc.
        logger.info(f"Token validated: subject={claims.get('sub')}")

        return claims

    except JoseError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token signature or claims")
    except Exception as e:
        logger.exception("Unexpected error during token validation")
        raise HTTPException(status_code=401, detail=str(e))
