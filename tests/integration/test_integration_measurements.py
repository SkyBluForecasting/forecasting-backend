"""Integration tests for the /assets/{asset_uuid}/measurements APIs."""

from datetime import datetime, timezone

import pytest

from app.measurement_service import get_all_measurements


@pytest.mark.asyncio
async def test_post_measurements_inserts_and_persists(
    post_assets,
    post_measurements,
    test_session,
):
    """POST /assets/{asset_uuid}/measurements inserts rows and returns inserted_count."""
    # Ensure asset exists

    await post_assets(
        [
            {
                "id": "A1",
                "name": "Asset 1",
                "type": "system",
                "capacity_kw": 0.0,
                "measured": True,
                "assets": [],
            }
        ]
    )

    payload = {
        "measurements": [
            {"metric": "load", "timestamp": "2026-01-01T00:00:00+00:00", "value": 100.0},
            {"metric": "load", "timestamp": "2026-01-01T00:15:00+00:00", "value": 110.0},
            {"metric": "load", "timestamp": "2026-01-01T00:30:00+00:00", "value": 120.0},
        ]
    }

    resp = await post_measurements("A1", payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["asset_uuid"] == "A1"
    assert data["inserted_count"] == 3
    assert data["message"] == "Measurements inserted successfully"

    # Verify DB via service
    start_dt = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    measurements = await get_all_measurements(test_session, "A1", start_dt, end_dt)

    assert set(measurements.keys()) == {"metrics", "values", "units"}

    assert "load" in measurements["metrics"]
    assert "load" in measurements["units"]

    # values is [{"timestamp": "...", "values": {"load": 100.0, ...}}, ...]
    assert len(measurements["values"]) == 3
    assert [row["values"]["load"] for row in measurements["values"]] == [100.0, 110.0, 120.0]


@pytest.mark.asyncio
async def test_get_measurements_filters_by_time_window(
    post_assets,
    post_measurements,
    get_measurements,
):
    """GET /assets/{asset_uuid}/measurements returns only points within start/end."""
    await post_assets(
        [
            {
                "id": "A1",
                "name": "Asset 1",
                "type": "system",
                "capacity_kw": 0.0,
                "measured": True,
                "assets": [],
            }
        ]
    )

    payload = {
        "measurements": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "value": 1.0,
                "metric": "load",
            },
            {
                "timestamp": "2026-01-01T00:15:00+00:00",
                "value": 2.0,
                "metric": "load",
            },
            {
                "timestamp": "2026-01-01T00:30:00+00:00",
                "value": 3.0,
                "metric": "load",
            },
            {
                "timestamp": "2026-01-01T02:00:00+00:00",
                "value": 999.0,
                "metric": "load",
            },  # outside range
        ]
    }
    post_resp = await post_measurements("A1", payload)
    assert post_resp.status_code == 200

    resp = await get_measurements(
        "A1",
        params={
            "start_time": "2026-01-01T00:00:00+00:00",
            "end_time": "2026-01-01T01:00:00+00:00",
        },
    )
    assert resp.status_code == 200

    data = resp.json()
    assert set(data.keys()) == {"metrics", "units", "values"}
    assert "load" in data["metrics"]
    assert "load" in data["units"]

    # Only the three in-range points should appear
    assert [row["values"]["load"] for row in data["values"]] == [1.0, 2.0, 3.0]


@pytest.mark.asyncio
async def test_get_measurements_returns_empty_when_none_in_range(
    post_assets,
    post_measurements,
    get_measurements,
):
    """GET /assets/{asset_uuid}/measurements returns [] when no points match."""
    await post_assets(
        [
            {
                "id": "A1",
                "name": "Asset 1",
                "type": "system",
                "capacity_kw": 0.0,
                "measured": True,
                "assets": [],
            }
        ]
    )

    payload = {
        "measurements": [{"timestamp": "2026-01-01T00:00:00+00:00", "value": 5.0, "metric": "load"}]
    }
    post_resp = await post_measurements("A1", payload)
    assert post_resp.status_code == 200

    resp = await get_measurements(
        "A1",
        params={
            "start_time": "2026-01-01T01:00:00+00:00",
            "end_time": "2026-01-01T02:00:00+00:00",
        },
    )
    assert resp.status_code == 200

    data = resp.json()
    assert set(data.keys()) == {"metrics", "units", "values"}
    assert data["values"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start_time,end_time",
    [
        ("not-a-datetime", "2026-01-01T01:00:00+00:00"),
        ("2026-01-01T00:00:00+00:00", "bad"),
        ("2026-13-01T00:00:00+00:00", "2026-01-01T01:00:00+00:00"),
        ("2026-01-01T00:00:00", "2026-01-01T01:00:00+00:00"),
    ],
)
async def test_get_measurements_invalid_datetime_returns_400(
    get_measurements,
    start_time,
    end_time,
):
    """GET /assets/{asset_uuid}/measurements returns 400 on invalid ISO strings."""
    resp = await get_measurements(
        "A1",
        params={"start_time": start_time, "end_time": end_time},
    )

    if start_time.endswith("T00:00:00") and "+" not in start_time and "Z" not in start_time:
        assert resp.status_code in (200, 400)
    else:
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid datetime format, use ISO format"
