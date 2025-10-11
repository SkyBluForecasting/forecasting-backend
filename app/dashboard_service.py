"""Functions for pulling and parsing data to display in dashboard."""

from .db_utils import to_utc_iso
from .forecast_service import get_active_forecast, get_forecast_rows
from .measurement_service import get_all_measurements


async def get_dashboard_asset_data(asset_uuid: str):
    """Fetch dashboard data for a specific asset, including latest forecast and measurements.

    Args:
        asset_uuid (str): UUID of the asset to retrieve data for.
    Returns:
        dict: Dictionary containing the asset UUID, latest forecast information, and measurements.
              Structure matches the DashboardResponse schema:
              {
                  "asset_uuid": str,
                  "forecast": {
                      "forecast_uuid": str,
                      "run_uuid": str,
                      "values": List[Dict[str, Any]]  # timestamp and forecast_kw
                  } or None,
                  "measurements": Dict[str, Any] or None  # metrics and values
              }
    """
    # 1. Get Active Forecast
    latest_forecast = await get_active_forecast(asset_uuid)
    if not latest_forecast:
        return {
            "asset_uuid": asset_uuid,
            "forecast": None,
            "measurements": None,
        }

    forecast_run_id = latest_forecast["forecast_run_id"]

    # 2. Fetch forecast values
    forecast_values = await get_forecast_rows(forecast_run_id)
    start_time = forecast_values[0]["timestamp"] if forecast_values else None
    end_time = forecast_values[-1]["timestamp"] if forecast_values else None

    # 3. Fetch measurements
    measurements_values = (
        await get_all_measurements(asset_uuid, start_time, end_time)
        if start_time and end_time
        else {"metrics": [], "values": []}
    )

    # 4. Convert timestamps in forecast_values to ISO for API response
    forecast_values_iso = [
        {"timestamp": to_utc_iso(r["timestamp"]), "forecast_kw": r["forecast_kw"]}
        for r in forecast_values
    ]

    return {
        "asset_uuid": asset_uuid,
        "forecast": {
            "forecast_run_id": forecast_run_id,
            "model_run_id": latest_forecast.get("model_run_id"),
            "values": forecast_values_iso,
        },
        "measurements": measurements_values,
    }
