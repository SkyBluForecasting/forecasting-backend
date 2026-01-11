"""Functions for pulling and pushing forecast error metrics."""

from forecasting_db.models import ForecastError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_utils import to_utc_iso


async def get_forecast_errors(session: AsyncSession, run_id: str):
    """Return {timestamp_str: error} for a forecast run (timestamps in ISO UTC)."""
    q = select(ForecastError.timestamp, ForecastError.error).where(
        ForecastError.forecast_run_id == run_id
    )
    rows = (await session.execute(q)).mappings().all()

    # Convert datetime keys to ISO strings
    return {to_utc_iso(row["timestamp"]): row["error"] for row in rows}
