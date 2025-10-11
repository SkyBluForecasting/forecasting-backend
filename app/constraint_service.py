"""Functions for pulling and parsing constraint data from DB."""

import logging
from typing import Optional

from forecasting_db.models import Constraint, ForecastRun
from sqlalchemy import Integer, cast, select, text
from sqlalchemy.orm import aliased

from .db_client import AsyncSessionLocal
from .db_utils import to_utc_iso

logger = logging.getLogger(__name__)


def format_constraints_rows(rows: list[dict]) -> dict:
    """
    Convert raw database rows into structured dict for API response.

    Args:
        rows: List of dicts from SQLAlchemy query.

    Returns:
        dict: Dictionary matching ActiveConstraintsResponse schema.
    """
    assets_dict = {}
    for r in rows:
        a_uuid = r["asset_uuid"]

        constraint = {
            "start_time": to_utc_iso(r["start_time"]),
            "end_time": to_utc_iso(r["end_time"]),
            "constraint_kw": r["constraint_kw"],
        }

        if a_uuid not in assets_dict:
            assets_dict[a_uuid] = {
                "asset_uuid": a_uuid,
                "forecast_run_id": str(r["forecast_run_id"]),
                "frequency_min": r["frequency_min"],
                "constraints": [],
            }

        assets_dict[a_uuid]["constraints"].append(constraint)

    return {"assets": list(assets_dict.values())}


async def get_active_constraints(asset_uuid: Optional[str] = None) -> dict:
    """
    Get active constraints for assets.

    Args:
        asset_uuid: Optional asset UUID to filter by.

    Returns:
        dict: Dictionary matching ActiveConstraintsResponse schema.
    """
    async with AsyncSessionLocal() as session:
        # Latest forecast run per asset
        latest_forecasts_subq = (
            select(
                ForecastRun.asset_uuid,
                ForecastRun.forecast_run_id,
                ForecastRun.frequency_min,
                ForecastRun.created_at,
            )
            .distinct(ForecastRun.asset_uuid)
            .order_by(ForecastRun.asset_uuid, ForecastRun.created_at.desc())
            .subquery()
        )

        lf = aliased(latest_forecasts_subq)

        # Calculate end time of constraint
        end_time_expr = (
            Constraint.timestamp + cast(lf.c.frequency_min, Integer) * text("interval '1 minute'")
        ).label("end_time")

        # Join constraints with latest forecast runs
        q = select(
            Constraint.asset_uuid,
            Constraint.forecast_run_id,
            Constraint.timestamp.label("start_time"),
            end_time_expr,
            Constraint.constraint_kw,
            lf.c.frequency_min,
        ).join(lf, Constraint.forecast_run_id == lf.c.forecast_run_id)

        if asset_uuid:
            q = q.where(lf.c.asset_uuid == asset_uuid)

        q = q.order_by(lf.c.asset_uuid, Constraint.timestamp)

        result = await session.execute(q)
        rows = result.mappings().all()

    return format_constraints_rows(rows)
