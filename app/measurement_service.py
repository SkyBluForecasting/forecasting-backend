"""Functions for pulling and parsing measurements."""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from forecasting_db.models import Forecast, ForecastError, ForecastRun, Measurement
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db_client import AsyncSessionLocal
from .db_utils import to_utc, to_utc_iso

logger = logging.getLogger(__name__)

METRIC_UNITS = {
    "load": "kW",
    "temp": "C",
}

CHUNK_SIZE = 200  # safe default


async def insert_measurements(asset_uuid: str, measurements: list) -> dict:
    """Insert measurements (and resulting forecast errors) into the DB."""
    if not measurements:
        return {"status": "no data provided"}

    async with AsyncSessionLocal() as session:
        total_inserted = 0

        for i in range(0, len(measurements), CHUNK_SIZE):
            chunk = measurements[i : i + CHUNK_SIZE]

            # Deduplicate within this chunk by (asset_uuid, timestamp, metric)
            unique_rows = {}
            for m in chunk:
                key = (asset_uuid, to_utc(m["timestamp"]), m["metric"])
                unique_rows[key] = {
                    "asset_uuid": asset_uuid,
                    "timestamp": to_utc(m["timestamp"]),
                    "metric": m["metric"],
                    "value": m["value"],
                }

            rows = list(unique_rows.values())

            stmt = pg_insert(Measurement).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["asset_uuid", "timestamp", "metric"],
                set_={"value": stmt.excluded.value},
            )

            await session.execute(stmt)
            total_inserted += len(rows)

        await session.commit()
        await _insert_forecast_errors_for_new_measurements(
            session, asset_uuid, list(unique_rows.values())
        )

    return {"status": "success", "inserted": total_inserted}


async def get_all_measurements(asset_uuid: str, start_time: datetime, end_time: datetime) -> Dict:
    """Return all measurements grouped by timestamp with all metrics."""
    async with AsyncSessionLocal() as session:
        start_time_utc = to_utc(start_time)
        end_time_utc = to_utc(end_time)

        q = (
            select(Measurement.timestamp, Measurement.metric, Measurement.value)
            .where(
                (Measurement.asset_uuid == asset_uuid)
                & (Measurement.timestamp >= start_time_utc)
                & (Measurement.timestamp <= end_time_utc)
            )
            .order_by(Measurement.timestamp)
        )
        result = await session.execute(q)
        rows = result.mappings().all()

    if not rows:
        return {"metrics": [], "values": [], "units": {}}

    # pivot rows by timestamp
    grouped = defaultdict(dict)
    metrics_set = set(METRIC_UNITS.keys())

    for r in rows:
        ts = to_utc_iso(r["timestamp"])
        grouped[ts][r["metric"]] = r["value"]
        metrics_set.add(r["metric"])

    # Ensure every timestamp has all metrics (fill missing with None)
    for ts_values in grouped.values():
        for metric in metrics_set:
            ts_values.setdefault(metric, None)

    # convert to list of dicts with a 'values' dict
    values = [{"timestamp": ts, "values": metrics} for ts, metrics in sorted(grouped.items())]

    return {
        "metrics": sorted(metrics_set),
        "values": values,
        "units": {metric: METRIC_UNITS.get(metric, "") for metric in metrics_set},
    }


def _compute_forecast_errors(forecasts: List[Dict], measurements: List[Dict]) -> List[Dict]:
    """
    Pure function: compute forecast errors for a list of forecasts and load measurements.

    Args:
        forecasts: List of dicts with keys ['timestamp', 'forecast_run_id', 'forecast_value']
        measurements: List of dicts with keys ['timestamp', 'metric', 'value']

    Returns:
        List of dicts with keys ['forecast_run_id', 'timestamp', 'error']
    """
    # Map forecasts by timestamp for quick lookup
    forecast_map = defaultdict(list)
    for f in forecasts:
        forecast_map[f["timestamp"]].append(f)

    error_rows = []
    for m in measurements:
        ts = m["timestamp"]
        val = m["value"]

        for f in forecast_map.get(ts, []):
            error_rows.append(
                {
                    "forecast_run_id": f["forecast_run_id"],
                    "timestamp": ts,
                    "error": f["forecast_value"] - val,
                }
            )

    return error_rows


async def _insert_forecast_errors_for_new_measurements(
    session, asset_uuid: str, new_measurements: list
):
    """
    Compute and insert forecast errors for newly inserted *load* measurements.

    Keeps original working signature for insert_measurements().
    """
    # Filter to 'load' metric only
    load_measurements = [m for m in new_measurements if m.get("metric") == "load"]
    if not load_measurements:
        return

    new_timestamps = [to_utc(m["timestamp"]) for m in load_measurements]

    q = (
        select(Forecast.timestamp, Forecast.forecast_run_id, Forecast.forecast_value)
        .join(ForecastRun, Forecast.forecast_run_id == ForecastRun.forecast_run_id)
        .where((ForecastRun.asset_uuid == asset_uuid) & (Forecast.timestamp.in_(new_timestamps)))
    )
    result = await session.execute(q)
    forecasts = result.mappings().all()

    if not forecasts:
        logger.info(
            f"[{asset_uuid}] No forecasts found overlapping {len(new_timestamps)} new timestamps."
        )
        return

    # Use the pure function for computation
    error_rows = _compute_forecast_errors(forecasts, load_measurements)

    if not error_rows:
        logger.info(
            f"[{asset_uuid}] Found forecasts but no matching timestamps for error computation."
        )
        return

    stmt = pg_insert(ForecastError).values(error_rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["forecast_run_id", "timestamp"])
    await session.execute(stmt)
    await session.commit()

    logger.info(
        f"[{asset_uuid}] Computed {len(error_rows)} forecast errors for "
        f"{len(load_measurements)} new load measurements "
        f"({len(forecasts)} forecasts found)."
    )
