"""S3 module for handling forecast data storage and retrieval."""

import json
import logging
import os

import boto3
from fastapi import HTTPException

DEFAULT_S3_BUCKET = os.getenv("S3_BUCKET")
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


def get_latest_forecast(asset_id: str, s3=None, bucket_name: str = None):
    """Get the latest forecast from S3 for a specific asset.

    Args:
        asset_id: The asset identifier.
        s3: Optional boto3 S3 client (used for testing).
        bucket_name: Optional S3 bucket name (defaults to env var).

    Returns:
        dict: The latest forecast data.

    Raises:
        HTTPException: If the forecast cannot be retrieved.
    """
    logger.info("Getting latest forecast for asset_id=%s", asset_id)
    prefix = f"forecasts/{asset_id}/"
    bucket_name = bucket_name or DEFAULT_S3_BUCKET

    if not bucket_name:
        logger.error("No S3 bucket name configured.")
        raise HTTPException(status_code=500, detail="Missing S3 bucket configuration.")

    try:
        s3 = s3 or get_s3_client()
        resp = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        logger.info(f"S3 response: {resp}")

        if "Contents" not in resp or not resp["Contents"]:
            logger.error(f"No forecasts found for prefix: {prefix}")
            raise HTTPException(status_code=404, detail="No forecasts found")

        latest = sorted(resp["Contents"], key=lambda x: x["Key"], reverse=True)[0]
        obj = s3.get_object(Bucket=bucket_name, Key=latest["Key"])
        return json.loads(obj["Body"].read())
    except HTTPException:
        # Re-raise HTTPExceptions so they keep their original status code
        raise

    except Exception as e:
        logger.error(f"Error getting latest forecast: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving latest forecast: {str(e)}"
        )
