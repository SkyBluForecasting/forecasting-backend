"""Unit tests for the S3 integration functions in app.s3 module."""

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import NoCredentialsError
from fastapi import HTTPException

import app
from app.s3 import get_latest_forecast, get_s3_client


def test_get_s3_client_raises_http_exception_on_failure():
    """Test that get_s3_client raises an HTTPException with status 500.

    when boto3.client fails to create an S3 client (e.g., due to missing credentials).
    """
    with patch("boto3.client") as mock_boto_client:
        # Simulate boto3.client("s3") raising an exception
        mock_boto_client.side_effect = NoCredentialsError()

        with pytest.raises(HTTPException) as exc:
            get_s3_client()

        assert exc.value.status_code == 500
        assert exc.value.detail == "Failed to connect to S3"


def test_get_latest_forecast_success():
    """Test successful retrieval of the latest forecast from S3.

    Mocks S3 client to return a forecast object, verifies that
    the function returns the correct parsed JSON data.
    """
    mock_s3 = Mock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "forecasts/asset123/2025-07-04T12:00:00.json"}]
    }
    mock_s3.get_object.return_value = {
        "Body": Mock(read=Mock(return_value=b'{"temp": 22}'))
    }

    result = get_latest_forecast("asset123", s3=mock_s3, bucket_name="my-test-bucket")
    assert result == {"temp": 22}


def test_get_latest_forecast_no_contents():
    """Test get_latest_forecast raises HTTPException with 404 status.

    when S3 list_objects_v2 returns 'Contents' as an empty list (no forecasts).
    """
    mock_s3 = Mock()
    mock_s3.list_objects_v2.return_value = {"Contents": []}

    with pytest.raises(HTTPException) as exc:
        get_latest_forecast("asset123", s3=mock_s3, bucket_name="my-test-bucket")

    assert exc.value.status_code == 404
    assert "No forecasts found" in exc.value.detail


def test_get_latest_forecast_no_key():
    """Test get_latest_forecast raises HTTPException with 404 status.

    when S3 list_objects_v2 response does not include 'Contents' key.
    """
    mock_s3 = Mock()
    mock_s3.list_objects_v2.return_value = {}

    with pytest.raises(HTTPException) as exc:
        get_latest_forecast("asset123", s3=mock_s3, bucket_name="my-test-bucket")

    assert exc.value.status_code == 404
    assert "No forecasts found" in exc.value.detail


def test_get_latest_forecast_exception_on_get_object():
    """Test get_latest_forecast raises HTTPException with 500 status.

    when an exception occurs during S3 get_object call.
    """
    mock_s3 = Mock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "forecasts/asset123/2025-07-04T12:00:00.json"}]
    }
    mock_s3.get_object.side_effect = Exception("S3 failure")

    with pytest.raises(HTTPException) as exc:
        get_latest_forecast("asset123", s3=mock_s3, bucket_name="my-test-bucket")

    assert exc.value.status_code == 500
    assert "Error retrieving latest forecast" in exc.value.detail


def test_get_latest_forecast_missing_bucket():
    """Test get_latest_forecast raises HTTPException with 500 status.

    if the S3 bucket name configuration is missing (None).
    """
    mock_s3 = Mock()

    with patch("app.s3.DEFAULT_S3_BUCKET", None):
        with pytest.raises(HTTPException) as exc:
            get_latest_forecast("asset123", s3=mock_s3, bucket_name=None)

        assert exc.value.status_code == 500
        assert "Missing S3 bucket configuration" in exc.value.detail
