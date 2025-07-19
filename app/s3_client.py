"""S3 module for handling forecast data storage and retrieval."""

import logging
import os

import boto3
from dotenv import load_dotenv
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

S3_BUCKET = os.getenv("S3_BUCKET")


def get_s3_bucket():
    """Return the S3 bucket name from the environment.

    Returns:
        S3 bucket
    Raises:
        HTTPException if missing.
    """
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise HTTPException(
            status_code=500, detail="S3_BUCKET environment variable is not set."
        )
    return bucket


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


def list_objects(s3, bucket, prefix):
    """List objects in the specified S3 bucket with the given prefix."""
    return s3.list_objects_v2(Bucket=bucket, Prefix=prefix)


def get_object(s3, bucket, key):
    """Retrieve an object from the specified S3 bucket using its key."""
    return s3.get_object(Bucket=bucket, Key=key)
