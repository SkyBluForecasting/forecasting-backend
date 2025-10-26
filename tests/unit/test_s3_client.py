"""Unit tests for the S3 integration functions in app.s3 module."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.s3_client import get_object, get_s3_bucket, get_s3_client, list_objects


class TestGetS3Bucket:
    """Tests for the get_s3_bucket function."""

    def test_get_s3_bucket_returns_value(self, set_s3_env):
        """Returns the S3 bucket name when environment variable is set."""
        assert get_s3_bucket() == "my-test-bucket"

    def test_get_s3_bucket_raises_if_missing(self, monkeypatch):
        """Raises HTTPException if S3_BUCKET environment variable is missing."""
        monkeypatch.delenv("S3_BUCKET", raising=False)
        with pytest.raises(HTTPException) as exc_info:
            get_s3_bucket()
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "S3_BUCKET environment variable is not set."


class TestGetS3Client:
    """Tests for the get_s3_client function."""

    def test_get_s3_client_success(self):
        """Successfully returns a boto3 S3 client instance."""
        s3 = get_s3_client()
        assert s3 is not None
        assert type(s3).__module__.startswith("botocore.client")

    def test_get_s3_client_raises_http_exception_on_failure(self):
        """Raises HTTPException if boto3 client creation fails."""
        with patch("app.s3_client.boto3.client", side_effect=Exception("mock error")):
            with pytest.raises(HTTPException) as exc_info:
                get_s3_client()
            assert exc_info.value.status_code == 500
            assert exc_info.value.detail == "Failed to connect to S3"


class TestListObjects:
    """Tests for the list_objects function."""

    def test_list_objects_returns_expected_structure(self, s3_stub_client):
        """Returns expected dictionary structure from S3 list_objects_v2 call."""
        s3, stubber = s3_stub_client
        expected_response = {
            "Contents": [
                {
                    "Key": "forecasts/L9M/sample.csv",
                    "LastModified": "2025-07-16T00:00:00Z",
                }
            ]
        }

        stubber.add_response(
            "list_objects_v2",
            expected_response,
            {"Bucket": "test-bucket", "Prefix": "forecasts/L9M/"},
        )

        result = list_objects(s3, "test-bucket", "forecasts/L9M/")
        assert result == expected_response


class TestGetObject:
    """Tests for the get_object function."""

    def test_get_object_returns_file_content(self, s3_stub_client, forecast_csv_body):
        """Returns expected content when retrieving an S3 object."""
        s3, stubber = s3_stub_client
        expected_response = {"Body": forecast_csv_body}

        stubber.add_response(
            "get_object",
            expected_response,
            {"Bucket": "test-bucket", "Key": "forecasts/L9M/sample.csv"},
        )

        result = get_object(s3, "test-bucket", "forecasts/L9M/sample.csv")
        content = result["Body"].read().decode("utf-8")
        assert "datetime" in content
        assert "123.45" in content
