"""
Pytest configuration file to set up environment variables and fixtures.

This file sets required environment variables (e.g., S3_BUCKET) at import time
so they are available when application modules are imported during testing.

It can also contain shared fixtures for all tests in the test suite.
"""

import os

os.environ["S3_BUCKET"] = "dummy-bucket"
