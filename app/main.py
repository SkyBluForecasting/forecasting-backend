"""Main FastAPI application module for serving forecast endpoints."""

import logging

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import validate_token
from .s3 import get_forecast, get_latest_forecast

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

    Raises:
        HTTPException: If the authorization header is missing.
    """
    # Log the full raw Authorization header as received in the HTTP request
    raw_auth_header = request.headers.get("Authorization")
    logger.info(f"Raw Authorization header: {repr(raw_auth_header)}")

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = (
        credentials.credentials.strip()
    )  # FastAPI's HTTPBearer already strips "Bearer "

    logger.info(
        f"Token format check - Length: {len(token)}, First 20 chars: {token[:20]}"
    )

    return token


@app.get("/forecast")
def read_forecast(
    utility_id: str, asset_id: str, date: str, token: str = Depends(get_token)
):
    """Get a forecast for a specific utility, asset, and date.

    Args:
        utility_id: The utility identifier.
        asset_id: The asset identifier.
        date: The date of the forecast.
        token: The JWT token for authentication.

    Returns:
        dict: The forecast data.
    """
    validate_token(token)
    return get_forecast(utility_id, asset_id, date)


@app.get("/forecast/latest")
def read_latest_forecast(
    utility_id: str, asset_id: str, token: str = Depends(get_token)
):
    """Get the latest forecast for a specific utility and asset.

    Args:
        utility_id: The utility identifier.
        asset_id: The asset identifier.
        token: The JWT token for authentication.

    Returns:
        dict: The latest forecast data.
    """
    validate_token(token)
    return get_latest_forecast(utility_id, asset_id)
