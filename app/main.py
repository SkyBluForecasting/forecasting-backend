"""Main FastAPI application module for serving forecast endpoints."""

import logging

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import validate_token
from .forecast_service import get_latest_forecast

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Forecasting API",
    description="API for serving solar/load forecasts",
    version="1.0.0",
)

security = HTTPBearer()


async def get_token(
    request: Request, credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """Extract and validate the JWT token from the Authorization header.

    Args:
        request: The FastAPI request object.
        credentials: The HTTP authorization credentials.

    Returns:
        str: The extracted JWT token.

    Notes:
            - If the Authorization header is missing or invalid, FastAPI's
            HTTPBearer will return a 403 before this function is called.
    """
    # Log the full raw Authorization header as received in the HTTP request
    raw_auth_header = request.headers.get("Authorization")
    logger.info(f"Raw Authorization header: {repr(raw_auth_header)}")

    token = (
        credentials.credentials.strip()
    )  # FastAPI's HTTPBearer already strips "Bearer "

    logger.info(
        f"Token format check - Length: {len(token)}, First 20 chars: {token[:20]}"
    )

    return token


@app.get("/forecast/latest")
def read_latest_forecast(asset_id: str, token: str = Depends(get_token)):
    """Get the latest forecast for a specific asset.

    Args:
        asset_id: The asset identifier.
        token: The JWT token for authentication.

    Returns:
        dict: The latest forecast data.
    """
    validate_token(token)
    return get_latest_forecast(asset_id)
