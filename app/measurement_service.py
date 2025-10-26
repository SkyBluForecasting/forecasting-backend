"""Functions for pulling and parsing measurements."""

from collections import defaultdict
from datetime import datetime
from typing import Dict

from forecasting_db.models import Measurement
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db_client import AsyncSessionLocal
from .db_utils import to_utc, to_utc_iso

METRIC_UNITS = {
    "load": "kW",
    "temp": "C",
}


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


CHUNK_SIZE = 200  # safe default


async def insert_measurements(asset_uuid: str, measurements: list) -> dict:
    """Insert measurements into the DB."""
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

    return {"status": "success", "inserted": total_inserted}
