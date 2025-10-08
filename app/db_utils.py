"""Utils for handling db data."""

from datetime import timezone


def to_utc(dt):
    """Convert datetime to UTC (returns a datetime object)."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc)


def to_utc_iso(dt):
    """Convert datetime to ISO 8601 string in UTC (for API response)."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
