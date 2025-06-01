"""Configuration module for managing environment variables and Auth0 settings."""

import json
import logging
import os

import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME")

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
AUTH0_ALGORITHMS = ["RS256"]

# Cache for Auth0 JWKS
_jwks_cache = None


def get_jwks():
    """Get the JSON Web Key Set (JWKS) from Auth0.

    Returns:
        dict: The JWKS data.

    Raises:
        ValueError: If AUTH0_DOMAIN is not set.
        requests.exceptions.RequestException: If the JWKS request fails.
        json.JSONDecodeError: If the JWKS response is not valid JSON.
    """
    global _jwks_cache
    if _jwks_cache is None:
        try:
            # Use the full domain including region
            jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
            logger.info(f"Fetching JWKS from: {jwks_url}")

            if not AUTH0_DOMAIN:
                raise ValueError("AUTH0_DOMAIN is not set in environment variables")

            response = requests.get(jwks_url)
            response.raise_for_status()  # Raise an exception for bad status codes

            logger.info(f"JWKS response status: {response.status_code}")
            logger.info(
                f"JWKS response content: {response.text[:200]}..."
            )  # Log first 200 chars

            _jwks_cache = response.json()
            return _jwks_cache
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch JWKS: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JWKS response: {str(e)}")
            logger.error(f"Response content: {response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching JWKS: {str(e)}")
            raise
    return _jwks_cache
