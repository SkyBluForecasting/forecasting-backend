"""Main FastAPI application module for serving forecast endpoints."""

import logging
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .asset_service import fetch_assets, upsert_assets
from .auth import validate_token
from .constraint_service import get_active_constraints
from .dashboard_service import get_dashboard_asset_data
from .db_client import close_db_pool, get_db
from .measurement_service import get_all_measurements, insert_measurements
from .schemas import (
    ActiveConstraintsResponse,
    AssetIn,
    AssetResponse,
    AssetUpsertResponse,
    DashboardResponse,
    MeasurementInsertResponse,
    MeasurementsBatch,
    MeasurementsResponse,
)

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Forecasting API",
    description="SkyBlu Forecasting API Schema",
    version="1.0.0",
)


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on app shutdown."""
    await close_db_pool()  # Uses db_client’s pool cleanup


security = HTTPBearer()


async def get_session() -> AsyncSession:
    """Dependency wrapper for production or test session."""
    async for session in get_db():
        yield session


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
    "/dashboard/assets/{asset_uuid}/data",
    response_model=DashboardResponse,
    summary="Get dashboard data for an asset",
    description="Returns the last two forecasts (+ available measurements) for a specific asset.",
)
async def read_dashboard_asset_data(
    asset_uuid: str,
    token: str = Depends(get_token),
    session: AsyncSession = Depends(get_session),
):
    """Fetch forecast and measurement dashboard data for a specific asset."""
    validate_token(token)
    return await get_dashboard_asset_data(session, asset_uuid)


@app.post(
    "/assets/{asset_uuid}/measurements/",
    response_model=MeasurementInsertResponse,
    summary="Insert measurements for an asset",
    description="Insert one or more measurement points for the given asset.",
)
async def post_measurements(
    asset_uuid: str,
    data: MeasurementsBatch,
    token: str = Depends(get_token),
    session: AsyncSession = Depends(get_session),
):
    """Insert new measurements for an asset."""
    validate_token(token)
    await insert_measurements(session, asset_uuid, [m.dict() for m in data.measurements])
    return MeasurementInsertResponse(
        asset_uuid=asset_uuid,
        inserted_count=len(data.measurements),
        message="Measurements inserted successfully",
    )


@app.get(
    "/assets/{asset_uuid}/measurements/",
    response_model=MeasurementsResponse,
    summary="Get measurements for an asset",
    description="Fetch existing measurements for a specific asset within a time range.",
)
async def get_measurements(
    asset_uuid: str,
    start_time: str,
    end_time: str,
    token: str = Depends(get_token),
    session: AsyncSession = Depends(get_session),
):
    """Retrieve measurements for an asset."""
    validate_token(token)

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format, use ISO format")

    measurements = await get_all_measurements(session, asset_uuid, start_dt, end_dt)
    return measurements


@app.post(
    "/assets",
    response_model=AssetUpsertResponse,
    summary="Add or update assets",
    description="Creates new assets or updates existing ones. Does not delete any records.",
)
async def post_assets(
    assets: List[AssetIn] = Body(...),
    token: str = Depends(get_token),
    session: AsyncSession = Depends(get_session),
):
    """Add or update multiple assets without deleting existing ones."""
    validate_token(token)
    return await upsert_assets(session, assets)


@app.get(
    "/assets",
    response_model=List[AssetResponse],
    summary="Get assets",
    description="Returns all asset records, or filters by ID if provided.",
)
async def get_assets(
    asset_uuid: Optional[str] = None,
    token: str = Depends(get_token),
    session: AsyncSession = Depends(get_session),
):
    """Get assets from DB."""
    validate_token(token)
    return await fetch_assets(session, asset_uuid)
