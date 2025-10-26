"""Unit tests for db_utils module."""

from datetime import datetime, timezone

from app.db_utils import to_utc, to_utc_iso


def test_to_utc_none():
    """to_utc should return None when input is None."""
    assert to_utc(None) is None


def test_to_utc_converts_to_utc():
    """to_utc should convert naive or non-UTC datetime to UTC."""
    dt = datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc)
    result = to_utc(dt)
    assert result.tzinfo == timezone.utc
    assert result == dt


def test_to_utc_iso_none():
    """to_utc_iso should return None when input is None."""
    assert to_utc_iso(None) is None


def test_to_utc_iso_converts_to_iso():
    """to_utc_iso should return ISO 8601 string in UTC with 'Z' suffix."""
    dt = datetime(2025, 10, 7, 12, 0, tzinfo=timezone.utc)
    iso_str = to_utc_iso(dt)
    assert iso_str == "2025-10-07T12:00:00Z"
