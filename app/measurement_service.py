"""Functions for pulling and parsing measurements."""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from forecasting_db.models import Measurement  # updated model name
from sqlalchemy import insert, select

from .db_client import AsyncSessionLocal
from .db_utils import to_utc, to_utc_iso


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
        return {"metrics": [], "values": []}

    # pivot rows by timestamp
    grouped = defaultdict(dict)
    metrics_set = set()
    for r in rows:
        ts = to_utc_iso(r["timestamp"])
        grouped[ts][r["metric"]] = r["value"]
        metrics_set.add(r["metric"])

    # convert to list of dicts
    values = [{"timestamp": ts, **metrics} for ts, metrics in sorted(grouped.items())]

    return {"metrics": sorted(metrics_set), "values": values}


async def insert_measurements(asset_uuid: str, measurements: List[Dict]) -> Dict:
    """Insert a batch of measurement rows into the DB."""
    if not measurements:
        return {"status": "no data provided"}

    async with AsyncSessionLocal() as session:
        rows = [
            {
                "asset_uuid": asset_uuid,
                "timestamp": to_utc(m["timestamp"]),
                "metric": m["metric"],
                "value": m["value"],
            }
            for m in measurements
        ]

        stmt = insert(Measurement).values(rows)
        await session.execute(stmt)
        await session.commit()

    return {"status": "success", "inserted": len(rows)}
