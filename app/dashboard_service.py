"""Functions for pulling and parsing data to display in dashboard."""

from .db_utils import to_utc_iso
from .forecast_service import get_forecast_rows, get_recent_forecasts
from .measurement_service import METRIC_UNITS, get_all_measurements


async def get_dashboard_asset_data(asset_uuid: str):
    """Fetch dashboard data for an asset, including latest two forecasts and measurements."""
    # Get last two forecasts
    forecasts = await get_recent_forecasts(asset_uuid, limit=2)
    if not forecasts:
        return {
            "asset_uuid": asset_uuid,
            "latest_forecasts": [],
            "previous_forecasts": [],
            "measurements": None,
        }

    # The latest one is active, second is inactive
    latest_forecast = forecasts[0]
    second_forecast = forecasts[1] if len(forecasts) > 1 else None

    # Fetch values for both
    latest_values = await get_forecast_rows(latest_forecast["forecast_run_id"])
    inactive_values = (
        await get_forecast_rows(second_forecast["forecast_run_id"]) if second_forecast else []
    )

    # Determine overall time range for measurements
    start_time = (
        min(latest_values[0]["timestamp"], inactive_values[0]["timestamp"])
        if latest_values and inactive_values
        else latest_values[0]["timestamp"] if latest_values else None
    )
    end_time = (
        max(latest_values[-1]["timestamp"], inactive_values[-1]["timestamp"])
        if latest_values and inactive_values
        else latest_values[-1]["timestamp"] if latest_values else None
    )

    # Fetch measurements
    if start_time and end_time:
        measurements = await get_all_measurements(asset_uuid, start_time, end_time)
    else:
        measurements = {
            "metrics": [],
            "values": [],
            "units": {metric: METRIC_UNITS.get(metric, "") for metric in METRIC_UNITS},
        }

    async def format_forecast(run):
        values = await get_forecast_rows(run["forecast_run_id"])
        return {
            "forecast_run_id": run["forecast_run_id"],
            "model_run_id": run.get("model_run_id"),
            "values": [
                {"timestamp": to_utc_iso(v["timestamp"]), "forecast_kw": v["forecast_kw"]}
                for v in values
            ],
        }

    return {
        "asset_uuid": asset_uuid,
        "latest_forecasts": [await format_forecast(latest_forecast)],
        "previous_forecasts": ([await format_forecast(second_forecast)] if second_forecast else []),
        "measurements": measurements,
    }
