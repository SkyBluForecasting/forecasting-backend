"""Pydantic schemas for constraint-related data models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Constraint(BaseModel):
    """Represent a single time-based constraint for an asset."""

    start_time: Optional[datetime] = Field(None, example="2025-09-13T21:00:00Z")
    end_time: Optional[datetime] = Field(None, example="2025-09-13T22:00:00Z")
    constraint_kw: float = Field(..., example=38.081)


class AssetConstraints(BaseModel):
    """Represent constraints associated with a specific asset and forecast."""

    asset_uuid: str = Field(..., example="M4C")
    forecast_uuid: str = Field(..., example="11111111-1111-1111-1111-111111111111")
    frequency_min: int = Field(..., example=60)
    constraints: List[Constraint]


class ActiveConstraintsResponse(BaseModel):
    """Represent the response model containing active constraints per asset."""

    assets: List[AssetConstraints]


class DashboardResponse(BaseModel):
    """Represent active forecast and measurements for an asset."""

    asset_uuid: str
    forecast: Optional[Dict[str, Any]]
    measurements: Optional[Dict[str, Any]]


class MeasurementIn(BaseModel):
    """Single measurement input for an asset."""

    metric: str = Field(..., example="load_kw")
    timestamp: datetime = Field(..., example="2025-01-01T00:00:00Z")
    value: float = Field(..., example=1034.55)


class MeasurementsBatch(BaseModel):
    """Batch of measurements to insert for an asset."""

    measurements: List[MeasurementIn] = Field(
        ...,
        example=[
            {"metric": "load_kw", "timestamp": "2025-01-01T00:00:00Z", "value": 1034.55},
            {"metric": "temp_c", "timestamp": "2025-01-01T00:00:00Z", "value": -2.1},
        ],
    )
