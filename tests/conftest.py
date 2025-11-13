"""
Pytest configuration file to set up environment variables and fixtures.

This file sets required environment variables at import time
so they are available when application modules are imported during testing.

It can also contain shared fixtures for all tests in the test suite.
"""

import os


def pytest_configure():
    """Set env variables before test collection."""
    os.environ.setdefault("AUTH0_DOMAIN", "test-domain.auth0.com")
    os.environ.setdefault("AUTH0_AUDIENCE", "test-audience")
    # Database environment variables for testing
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_NAME", "test_forecasting")
    os.environ.setdefault("DB_USER", "test_user")
    os.environ.setdefault("DB_PASSWORD", "test_password")
