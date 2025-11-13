"""Functions for pulling and parsing forecast data."""

import logging

from forecasting_db.models import Forecast, ForecastRun
from sqlalchemy import select

from .db_client import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def get_active_forecast(asset_uuid: str):
    """Return latest forecast_run row for an asset as dict."""
    async with AsyncSessionLocal() as session:
        q = (
            select(
                ForecastRun.forecast_run_id,
                ForecastRun.prediction_job_id,
                ForecastRun.model_run_id,
                ForecastRun.asset_uuid,
                ForecastRun.created_at,
                ForecastRun.start_time,
                ForecastRun.end_time,
                ForecastRun.frequency_min,
            )
            .where(ForecastRun.asset_uuid == asset_uuid)
            .order_by(ForecastRun.created_at.desc())
            .limit(1)
        )
        result = await session.execute(q)
        row = result.mappings().first()
        return row


async def get_forecast_rows(forecast_run_id: str):
    """Return all forecast values for a forecast_run_id."""
    async with AsyncSessionLocal() as session:
        q = (
            select(Forecast.timestamp, Forecast.forecast_value)
            .where(Forecast.forecast_run_id == forecast_run_id)
            .order_by(Forecast.timestamp)
        )
        result = await session.execute(q)
        rows = result.mappings().all()

        # Return datetime objects with old key name to maintain existing format
        return [{"timestamp": r["timestamp"], "forecast_kw": r["forecast_value"]} for r in rows]


async def get_recent_forecasts(asset_uuid: str, limit: int = 2):
    """Return the most recent N forecast_run rows for an asset."""
    async with AsyncSessionLocal() as session:
        q = (
            select(
                ForecastRun.forecast_run_id,
                ForecastRun.prediction_job_id,
                ForecastRun.model_run_id,
                ForecastRun.asset_uuid,
                ForecastRun.created_at,
                ForecastRun.start_time,
                ForecastRun.end_time,
                ForecastRun.frequency_min,
            )
            .where(ForecastRun.asset_uuid == asset_uuid)
            .order_by(ForecastRun.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(q)
        rows = result.mappings().all()
        return rows
