"""Main FastAPI application module for serving forecast endpoints."""

import logging
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .asset_service import upsert_assets
from .auth import validate_token
from .constraint_service import get_active_constraints
from .dashboard_service import get_dashboard_asset_data
from .db_client import close_db_pool
from .forecast_service import get_latest_forecast
from .measurement_service import get_all_measurements, insert_measurements
from .schemas import (
    ActiveConstraintsResponse,
    AssetUpsertRequest,
    AssetUpsertResponse,
    DashboardResponse,
    MeasurementsBatch,
)

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
    await close_db_pool()  # Uses db_client’s pool cleanup


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

    token = credentials.credentials.strip()  # FastAPI's HTTPBearer already strips "Bearer "

    logger.info(f"Token format check - Length: {len(token)}, First 20 chars: {token[:20]}")

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


@app.get(
    "/dashboard/assets/{asset_uuid}/data/active",
    response_model=DashboardResponse,
    summary="Get active dashboard data for an asset",
    description="Returns the active forecast (+ available measurements) for a specific asset.",
)
async def read_dashboard_asset_data(
    asset_uuid: str,
    token: str = Depends(get_token),
):
    """Fetch active forecast and measurement dashboard data for a specific asset."""
    validate_token(token)
    return await get_dashboard_asset_data(asset_uuid)


@app.post(
    "/assets/{asset_uuid}/measurements/",
    summary="Insert measurements for an asset",
    description="Insert one or more measurement points for the given asset.",
)
async def post_measurements(
    asset_uuid: str,
    data: MeasurementsBatch,
    token: str = Depends(get_token),
):
    """Insert new measurements for an asset."""
    validate_token(token)
    return await insert_measurements(asset_uuid, [m.dict() for m in data.measurements])


@app.get(
    "/assets/{asset_uuid}/measurements/",
    summary="Get measurements for an asset",
    description="Fetch existing measurements for a specific asset within a time range.",
)
async def get_measurements(
    asset_uuid: str,
    start_time: str,
    end_time: str,
    token: str = Depends(get_token),
):
    """Retrieve measurements for an asset."""
    validate_token(token)

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format, use ISO format")

    measurements = await get_all_measurements(asset_uuid, start_dt, end_dt)
    return measurements


@app.post(
    "/assets",
    response_model=AssetUpsertResponse,
    summary="Add or update assets",
    description="Creates new assets or updates existing ones. Does not delete any records.",
)
async def post_assets(
    req: AssetUpsertRequest,
    token: str = Depends(get_token),
):
    """Add or update multiple assets without deleting existing ones."""
    validate_token(token)
    return await upsert_assets(req.assets)
