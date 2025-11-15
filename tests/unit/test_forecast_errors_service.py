"""Unit tests for forecast_errors_service.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db_utils import to_utc_iso
from app.forecast_errors_service import get_forecast_errors


@pytest.mark.asyncio
async def test_get_forecast_errors_empty():
    """Returns an empty dict when no forecast errors exist."""
    # Mock the result object returned by session.execute
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []

    # Mock the async session
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch("app.forecast_errors_service.AsyncSessionLocal", return_value=mock_session):
        result = await get_forecast_errors("run123")

    assert result == {}


@pytest.mark.asyncio
async def test_get_forecast_errors_single_row():
    """Returns correct dict when only one forecast error exists."""
    dt = datetime(2025, 11, 15, 12, 0, tzinfo=timezone.utc)
    rows = [{"timestamp": dt, "error": 3.5}]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch("app.forecast_errors_service.AsyncSessionLocal", return_value=mock_session):
        result = await get_forecast_errors("run123")

    assert result == {to_utc_iso(dt): 3.5}


@pytest.mark.asyncio
async def test_get_forecast_errors_multiple_rows():
    """Returns correct dict for multiple forecast errors."""
    dt1 = datetime(2025, 11, 15, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2025, 11, 15, 13, 0, tzinfo=timezone.utc)
    rows = [
        {"timestamp": dt1, "error": 1.0},
        {"timestamp": dt2, "error": -2.5},
    ]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value.execute.return_value = mock_result

    with patch("app.forecast_errors_service.AsyncSessionLocal", return_value=mock_session):
        result = await get_forecast_errors("run456")

    expected = {
        to_utc_iso(dt1): 1.0,
        to_utc_iso(dt2): -2.5,
    }
    assert result == expected
