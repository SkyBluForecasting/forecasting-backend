"""
Pytest configuration file to set up environment variables and fixtures.

This file sets required environment variables (e.g., S3_BUCKET) at import time
so they are available when application modules are imported during testing.

It can also contain shared fixtures for all tests in the test suite.
"""

import io
import os
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber


def pytest_configure():
    """Set env variables before test collection."""
    os.environ.setdefault("AUTH0_DOMAIN", "test-domain.auth0.com")
    os.environ.setdefault("AUTH0_AUDIENCE", "test-audience")


@pytest.fixture
def s3_stub_client():
    """Provide a boto3 S3 client with an activated Stubber for mocking AWS S3 calls.

    Yields:
        tuple: (boto3 S3 client, Stubber instance)
    """
    client = boto3.client("s3")
    stubber = Stubber(client)
    stubber.activate()
    yield client, stubber
    stubber.deactivate()


@pytest.fixture
def forecast_csv_body():
    """Provide a StreamingBody object containing sample CSV forecast data.

    Returns:
        StreamingBody: A streaming body containing CSV bytes for forecast data.
    """
    csv_data = b"datetime,forecast\n2025-07-16T00:00:00+00:00,123.45\n"
    return StreamingBody(io.BytesIO(csv_data), len(csv_data))


@pytest.fixture
def set_s3_env(monkeypatch):
    """Set the environment variable S3_BUCKET to a test value.

    Args:
        monkeypatch: pytest monkeypatch fixture to modify environment variables.
    """
    monkeypatch.setenv("S3_BUCKET", "my-test-bucket")


@pytest.fixture
def mock_s3_with_forecast(forecast_csv_body):
    """Provide a MagicMock S3 client with mocked get_object and list_objects_v2 methods.

    Args:
        forecast_csv_body (StreamingBody): The mocked CSV body fixture.

    Returns:
        MagicMock: A mocked S3 client with preset return values.
    """
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": forecast_csv_body}
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "forecasts/test/20240101.csv",
                "LastModified": "2025-07-16T00:00:00Z",
            }
        ],
        "KeyCount": 1,
        "IsTruncated": False,
        "Name": "forecasting-forecasts",
        "Prefix": "forecasts/test/",
    }
    return mock_s3
