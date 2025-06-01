"""S3 module for handling forecast data storage and retrieval."""

import json
import logging

import boto3
from fastapi import HTTPException

from .config import BUCKET_NAME

logger = logging.getLogger(__name__)


def get_s3_client():
    """Get a configured S3 client.

    Returns:
        boto3.client: Configured S3 client.

    Raises:
        HTTPException: If S3 client creation fails.
    """
    try:
        return boto3.client("s3")
    except Exception as e:
        logger.error(f"Failed to create S3 client: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect to S3")


def get_forecast(utility_id: str, asset_id: str, date: str):
    """Get a forecast from S3 for a specific utility, asset, and date.

    Args:
        utility_id: The utility identifier.
        asset_id: The asset identifier.
        date: The date of the forecast.

    Returns:
        dict: The forecast data.

    Raises:
        HTTPException: If the forecast cannot be retrieved.
    """
    logger.info(
        "Getting forecast for utility_id=%s, asset_id=%s, date=%s",
        utility_id,
        asset_id,
        date,
    )
    key = f"{utility_id}/{asset_id}/{date}.json"
    try:
        s3 = get_s3_client()
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        logger.error(f"Forecast not found: {key}")
        raise HTTPException(status_code=404, detail="Forecast not found")
    except Exception as e:
        logger.error(f"Error getting forecast: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving forecast: {str(e)}"
        )


def get_latest_forecast(utility_id: str, asset_id: str):
    """Get the latest forecast from S3 for a specific utility and asset.

    Args:
        utility_id: The utility identifier.
        asset_id: The asset identifier.

    Returns:
        dict: The latest forecast data.

    Raises:
        HTTPException: If the forecast cannot be retrieved.
    """
    logger.info(
        "Getting latest forecast for utility_id=%s, asset_id=%s",
        utility_id,
        asset_id,
    )
    prefix = f"{utility_id}/{asset_id}/"
    try:
        s3 = get_s3_client()
        resp = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        logger.info(f"S3 response: {resp}")

        if "Contents" not in resp or not resp["Contents"]:
            logger.error(f"No forecasts found for prefix: {prefix}")
            raise HTTPException(status_code=404, detail="No forecasts found")

        latest = sorted(resp["Contents"], key=lambda x: x["Key"], reverse=True)[0]
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=latest["Key"])
        return json.loads(obj["Body"].read())
    except Exception as e:
        logger.error(f"Error getting latest forecast: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving latest forecast: {str(e)}"
        )
