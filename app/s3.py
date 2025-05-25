import boto3
import json
from fastapi import HTTPException
from .config import BUCKET_NAME
import logging

logger = logging.getLogger(__name__)

def get_s3_client():
    try:
        return boto3.client("s3")
    except Exception as e:
        logger.error(f"Failed to create S3 client: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect to S3")

def get_forecast(utility_id: str, asset_id: str, date: str):
    logger.info(f"Getting forecast for utility_id={utility_id}, asset_id={asset_id}, date={date}")
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
        raise HTTPException(status_code=500, detail=f"Error retrieving forecast: {str(e)}")

def get_latest_forecast(utility_id: str, asset_id: str):
    logger.info(f"Getting latest forecast for utility_id={utility_id}, asset_id={asset_id}")
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
        raise HTTPException(status_code=500, detail=f"Error retrieving latest forecast: {str(e)}")
