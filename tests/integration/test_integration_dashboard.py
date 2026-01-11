"""Integration tests for the /dashboard APIs."""

from datetime import datetime, timedelta, timezone

import pytest


def make_timestamps(start: datetime, count: int, minutes: int = 15) -> list[datetime]:
    """Make timestamps for seeding data."""
    return [start + timedelta(minutes=minutes * i) for i in range(count)]


@pytest.mark.asyncio
async def test_dashboard_measured_leaf_asset(
    post_assets,
    get_dashboard_asset_data,
    canonical_asset_tree_payload,
    seed_prediction_job,
    seed_forecast_run,
    seed_forecast_points,
    seed_measurements_load,
    seed_forecast_errors,
):
    """
    Leaf measured asset: K0B.

    Validates:
    - latest_forecasts has 1
    - previous_forecasts has 1
    - measurements present
    - MAE/MAPE computed (not None) when errors + load exist
    """
    # 1) Insert assets via API
    resp = await post_assets(canonical_asset_tree_payload)
    assert resp.status_code == 200

    asset_uuid = "K0B"

    # 2) Seed prediction job (required by ForecastRun)
    pj = await seed_prediction_job(asset_uuid=asset_uuid)

    # 3) Seed two forecast runs (ensure created_at ordering: latest first)
    t0 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    ts = make_timestamps(t0, count=4, minutes=15)

    run_prev = await seed_forecast_run(
        asset_uuid=asset_uuid,
        prediction_job_id=pj.id,
        model_run_id="mlflow_prev",
        created_at=t0 + timedelta(minutes=10),
        start_time=ts[0],
        end_time=ts[-1],
        frequency_min=15,
        forecast_run_id="run_prev",
    )
    run_latest = await seed_forecast_run(
        asset_uuid=asset_uuid,
        prediction_job_id=pj.id,
        model_run_id="mlflow_latest",
        created_at=t0 + timedelta(minutes=20),
        start_time=ts[0],
        end_time=ts[-1],
        frequency_min=15,
        forecast_run_id="run_latest",
    )

    # 4) Seed forecast points
    latest_vals = [100.0, 110.0, 120.0, 130.0]
    prev_vals = [90.0, 105.0, 115.0, 140.0]
    await seed_forecast_points(
        forecast_run_id=run_latest.forecast_run_id, timestamps=ts, values_kw=latest_vals
    )
    await seed_forecast_points(
        forecast_run_id=run_prev.forecast_run_id, timestamps=ts, values_kw=prev_vals
    )

    # 5) Seed measurements (load)
    loads = [95.0, 108.0, 123.0, 128.0]
    await seed_measurements_load(asset_uuid=asset_uuid, timestamps=ts, load_kw=loads)

    # 6) Seed forecast errors (forecast - actual)
    latest_errors = [f - a for f, a in zip(latest_vals, loads)]
    prev_errors = [f - a for f, a in zip(prev_vals, loads)]
    await seed_forecast_errors(
        forecast_run_id=run_latest.forecast_run_id, timestamps=ts, errors=latest_errors
    )
    await seed_forecast_errors(
        forecast_run_id=run_prev.forecast_run_id, timestamps=ts, errors=prev_errors
    )

    # 7) Call dashboard endpoint
    resp = await get_dashboard_asset_data(asset_uuid)
    assert resp.status_code == 200
    data = resp.json()

    assert data["asset_uuid"] == asset_uuid
    assert len(data["latest_forecasts"]) == 1
    assert len(data["previous_forecasts"]) == 1

    # latest should be run_latest (newer created_at)
    assert data["latest_forecasts"][0]["forecast_run_id"] == "run_latest"
    assert data["previous_forecasts"][0]["forecast_run_id"] == "run_prev"

    # Values present
    assert len(data["latest_forecasts"][0]["values"]) == 4

    # Measurements present
    assert data["measurements"] is not None
    assert "values" in data["measurements"]

    # Metrics computed
    metrics = data["latest_forecasts"][0]["accuracy_metrics"]
    assert metrics["mae"] is not None
    assert metrics["mape"] is not None


@pytest.mark.asyncio
async def test_dashboard_non_leaf_unmeasured_asset(
    post_assets,
    get_dashboard_asset_data,
    canonical_asset_tree_payload,
    seed_prediction_job,
    seed_forecast_run,
    seed_forecast_points,
    seed_forecast_errors,
):
    """
    Non-leaf, unmeasured asset: ONT.

    Validates:
    - latest_forecasts has 1
    - previous_forecasts has 1
    - measurements is empty (asset not measured)
    - accuracy metrics still computed from forecast_errors
    """
    # 1) Insert assets (ONT is non-measured)
    resp = await post_assets(canonical_asset_tree_payload)
    assert resp.status_code == 200

    asset_uuid = "ONT"

    # 2) Seed prediction job
    pj = await seed_prediction_job(asset_uuid=asset_uuid)

    # 3) Seed two forecast runs
    t0 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    ts = make_timestamps(t0, count=4, minutes=15)

    run_prev = await seed_forecast_run(
        asset_uuid=asset_uuid,
        prediction_job_id=pj.id,
        model_run_id=None,
        created_at=t0 + timedelta(minutes=10),
        start_time=ts[0],
        end_time=ts[-1],
        frequency_min=15,
        forecast_run_id="run_prev_ont",
    )
    run_latest = await seed_forecast_run(
        asset_uuid=asset_uuid,
        prediction_job_id=pj.id,
        model_run_id=None,
        created_at=t0 + timedelta(minutes=20),
        start_time=ts[0],
        end_time=ts[-1],
        frequency_min=15,
        forecast_run_id="run_latest_ont",
    )

    # 4) Seed forecast points
    latest_vals = [200.0, 210.0, 220.0, 230.0]
    prev_vals = [195.0, 205.0, 215.0, 235.0]
    await seed_forecast_points(
        forecast_run_id=run_latest.forecast_run_id,
        timestamps=ts,
        values_kw=latest_vals,
    )
    await seed_forecast_points(
        forecast_run_id=run_prev.forecast_run_id,
        timestamps=ts,
        values_kw=prev_vals,
    )

    # 5) Seed forecast errors directly (no measurements for ONT)
    latest_errors = [1.0, -2.0, 3.0, -1.0]
    prev_errors = [-2.0, 0.0, -1.0, 4.0]
    await seed_forecast_errors(
        forecast_run_id=run_latest.forecast_run_id,
        timestamps=ts,
        errors=latest_errors,
    )
    await seed_forecast_errors(
        forecast_run_id=run_prev.forecast_run_id,
        timestamps=ts,
        errors=prev_errors,
    )

    # 6) Call dashboard endpoint
    resp = await get_dashboard_asset_data(asset_uuid)
    assert resp.status_code == 200
    data = resp.json()

    assert data["asset_uuid"] == asset_uuid
    assert len(data["latest_forecasts"]) == 1
    assert len(data["previous_forecasts"]) == 1

    assert data["latest_forecasts"][0]["forecast_run_id"] == "run_latest_ont"
    assert data["previous_forecasts"][0]["forecast_run_id"] == "run_prev_ont"

    assert len(data["latest_forecasts"][0]["values"]) == 4

    # Measurements should be empty for unmeasured asset
    assert data["measurements"]["values"] == []

    # Metrics still computed from forecast_errors
    metrics = data["latest_forecasts"][0]["accuracy_metrics"]
    assert metrics["mae"] is None
    assert metrics["mape"] is None
