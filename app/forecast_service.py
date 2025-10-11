"""Functions for pulling and parsing forecast data."""

import csv
import io
import logging

from fastapi import HTTPException
from forecasting_db.models import Forecast, ForecastRun
from sqlalchemy import select

from .db_client import AsyncSessionLocal
from .s3_client import get_object, get_s3_bucket, get_s3_client, list_objects

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


# TODO: Remove the following S3-related code after


def parse_forecast_csv(content: str) -> list[dict]:
    """Parse forecast CSV content into a structured list of dicts."""
    reader = csv.DictReader(io.StringIO(content))
    values = []

    for row in reader:
        try:
            # Handle index column as timestamp (row key is '')
            timestamp_raw = row["datetime"]
            forecast_val = float(row["forecast"])

            # Convert timestamp to Z-formatted ISO 8601
            # assuming it's already in ISO with +00:00
            timestamp = timestamp_raw.replace("+00:00", "Z")

            values.append({"timestamp": timestamp, "value_kw": forecast_val})

        except (KeyError, ValueError) as e:
            logger.warning(f"Skipping row due to error: {e}")

    return values


def get_latest_forecast(asset_id: str) -> dict:
    """Load and parse the latest forecast for an asset as a structured list of dicts.

    Args:
        asset_id (str): Asset ID whose forecast is to be generated.

    Returns:
        Dict: Dictionary with asset_id and forecast values

    Raises: TODOOO
        HTTPException: If S3 config is missing or no forecasts found
    """
    forecast = load_latest_forecast_data_from_s3(asset_id=asset_id)

    return {
        "asset_id": asset_id,
        "values": parse_forecast_csv(forecast),
    }


def load_latest_forecast_data_from_s3(asset_id) -> str:
    """
    Load the latest forecast data from S3.

    Returns:
        String of the forecast data
    Raises:
        HTTPException: If S3 config is missing or no forecasts found
    """
    prefix = f"forecasts/{asset_id}/"
    s3_bucket = get_s3_bucket()
    s3_client = get_s3_client()

    resp = list_objects(s3_client, s3_bucket, prefix)

    if "Contents" not in resp or not resp["Contents"]:
        raise HTTPException(status_code=404, detail="No forecasts found")

    latest = sorted(resp["Contents"], key=lambda x: x["LastModified"], reverse=True)[0]
    obj = get_object(s3_client, s3_bucket, latest["Key"])

    content = obj["Body"].read().decode("utf-8")

    return content
