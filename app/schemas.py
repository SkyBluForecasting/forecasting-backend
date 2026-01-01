"""Pydantic schemas for assets, forecasts, measurements, constraints, and dashboard responses."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from forecasting_db.models import AssetType
from pydantic import BaseModel, Field

# ============================================================
# 🟦 Asset Schemas
# ============================================================


class AssetResponse(BaseModel):
    """Schema returned when fetching asset records in a nested hierarchy."""

    asset_uuid: str
    name: str
    asset_type: str
    capacity_kw: Optional[float]
    parent_uuid: Optional[str]
    depth: int
    measured: bool
    children: List["AssetResponse"] = []


AssetResponse.update_forward_refs()


class AssetIn(BaseModel):
    """Schema for an individual asset received via API, including optional nested children."""

    id: str = Field(..., example="K0A")
    name: str = Field(..., example="K0A")
    type: AssetType = Field(..., example="distribution_substation")
    capacity_kw: Optional[float] = Field(None, example=80000.0)
    measured: bool = Field(False, example=True)
    assets: List["AssetIn"] = []


class AssetUpsertResponse(BaseModel):
    """Response summarizing the results of a bulk asset insertion or update."""

    inserted: int
    updated: int
    total: int


# ============================================================
# 🟩 Measurement Schemas
# ============================================================


class MeasurementIn(BaseModel):
    """Schema for a single measurement input for an asset."""

    metric: Literal["load", "temp"]
    timestamp: datetime
    value: float


class MeasurementsBatch(BaseModel):
    """Schema representing a batch of measurements to insert for a single asset."""

    measurements: List[MeasurementIn]


class MeasurementsValues(BaseModel):
    """Schema for measurement values at a specific timestamp."""

    timestamp: str
    values: Dict[str, Any]


class MeasurementsResponse(BaseModel):
    """Time-series measurement data with associated units."""

    metrics: List[str]
    units: Dict[str, str]  # e.g. {"load": "kW", "temp": "°C"}
    values: List[Dict[str, Any]]  # [{"timestamp": ..., "values": {...}}]


class MeasurementInsertResponse(BaseModel):
    """Response model after inserting measurements for a specific asset."""

    asset_uuid: str
    inserted_count: int
    message: str


# ============================================================
# 🟨 Forecast Schemas
# ============================================================


class ForecastValue(BaseModel):
    """Schema representing a single forecasted value at a specific timestamp."""

    timestamp: str
    forecast_kw: float


class AccuracyMetrics(BaseModel):
    """Schema representing accuracy metrics for a forecast run."""

    mae: Optional[float]
    mape: Optional[float]


class ForecastRun(BaseModel):
    """Schema representing a single forecast run for an asset."""

    forecast_run_id: str
    model_run_id: str
    values: List[ForecastValue]
    accuracy_metrics: Optional[AccuracyMetrics]


# ============================================================
# 🟥 Constraint Schemas
# ============================================================


class Constraint(BaseModel):
    """Schema representing a single time-based constraint for an asset."""

    start_time: Optional[datetime] = Field(None, example="2025-09-13T21:00:00Z")
    end_time: Optional[datetime] = Field(None, example="2025-09-13T22:00:00Z")
    constraint_kw: float = Field(..., example=38.081)


class AssetConstraints(BaseModel):
    """Schema representing constraints associated with a specific asset and forecast run."""

    asset_uuid: str = Field(..., example="M4C")
    forecast_run_id: str = Field(..., example="11111111-1111-1111-1111-111111111111")
    frequency_min: int = Field(..., example=60)
    constraints: List[Constraint]


class ActiveConstraintsResponse(BaseModel):
    """Schema representing the response containing all active constraints per asset."""

    assets: List[AssetConstraints]


# ============================================================
# 🟧 Dashboard Schema (aggregated response)
# ============================================================


class DashboardResponse(BaseModel):
    """Aggregated dashboard response containing active/inactive forecasts and measurements."""

    asset_uuid: str
    latest_forecasts: List[ForecastRun]
    previous_forecasts: List[ForecastRun]
    measurements: Optional[MeasurementsResponse]

    class Config:
        """Example data for Dashboard Response."""

        schema_extra = {
            "example": {
                "asset_uuid": "K0A",
                "latest_forecasts": [
                    {
                        "forecast_run_id": "forecast_run_1",
                        "model_run_id": "model_run_123",
                        "values": [
                            {"timestamp": "2025-10-20T03:00:00Z", "forecast_kw": 45.2},
                            {"timestamp": "2025-10-20T04:00:00Z", "forecast_kw": 46.1},
                        ],
                        "accuracy_metrics": {"mae": 4, "mape": 6},
                    }
                ],
                "previous_forecasts": [
                    {
                        "forecast_run_id": "forecast_run_0",
                        "model_run_id": "model_run_122",
                        "values": [
                            {"timestamp": "2025-10-19T03:00:00Z", "forecast_kw": 42.7},
                            {"timestamp": "2025-10-19T04:00:00Z", "forecast_kw": 43.5},
                        ],
                        "accuracy_metrics": {"mae": 4, "mape": 6},
                    }
                ],
                "measurements": {
                    "metrics": ["load", "temp"],
                    "units": {"load": "kW", "temp": "C"},
                    "values": [
                        {
                            "timestamp": "2025-10-20T03:00:00Z",
                            "values": {"load": 42.3, "temp": 15.4},
                        }
                    ],
                },
            }
        }
