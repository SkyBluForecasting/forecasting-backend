"""Main FastAPI application module for serving forecast endpoints."""

import logging
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import validate_token
from .constraint_service import get_active_constraints
from .db_client import close_db_pool
from .forecast_service import get_latest_forecast
from .schemas import ActiveConstraintsResponse

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Forecasting API",
    description="API for serving solar/load forecasts",
    version="1.0.0",
)


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on app shutdown."""
    await close_db_pool()


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


@app.get(
    "/constraints/active",
    response_model=ActiveConstraintsResponse,
    summary="Get active constraints for assets",
    description="Returns a list of active constraints grouped by asset.",
)
async def read_active_constraints(
    asset_uuid: Optional[str] = None, token: str = Depends(get_token)
):
    """Fetch active constraints for all assets or a specific asset."""
    validate_token(token)
    return await get_active_constraints(asset_uuid)
