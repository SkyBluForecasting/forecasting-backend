"""Integration test configuration and shared fixtures."""

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from forecasting_db.models import (
    Base,
    Forecast,
    ForecastError,
    ForecastRun,
    Measurement,
    PredictionJob,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app, get_session

############
# DB Set-Up Functions
#############


@pytest_asyncio.fixture
async def test_engine():
    """Async SQLAlchemy engine for the test database."""
    TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/test_forecasting_db"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS openstef;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS product;"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Async DB session bound to the test engine."""
    AsyncSessionLocal = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(test_session):
    """HTTPX async client with test DB session injected."""

    async def override_get_session():
        """Override FastAPI DB dependency."""
        yield test_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def clean_db(test_session):
    """Truncate all test tables before each test."""
    await test_session.execute(
        text(
            """
            TRUNCATE TABLE
                product.forecast_errors,
                product.constraints,
                openstef.forecast,
                openstef.forecast_runs,
                openstef.prediction_job,
                openstef.measurement,
                openstef.assets
            CASCADE;
            """
        )
    )
    await test_session.commit()


# ─── Auth helpers ───────────────────────────────────────────────


@asynccontextmanager
async def mocked_token():
    """Mock token validation."""
    with patch("app.main.validate_token") as mock_validate:
        mock_validate.return_value = True
        yield


# ─── API Helpers ───────────────────────────────────────────────


@pytest_asyncio.fixture
async def api_client(async_client):
    """Async client with auth mocked."""
    async with mocked_token():
        yield async_client


@pytest_asyncio.fixture
def post_assets(api_client):
    """POST /assets helper."""

    async def _post(payload):
        return await api_client.post(
            "/assets",
            json=payload,
            headers={"Authorization": "Bearer fake-token"},
        )

    return _post


@pytest_asyncio.fixture
def get_assets(api_client):
    """GET /assets helper."""

    async def _get(params=None):
        return await api_client.get(
            "/assets",
            params=params,
            headers={"Authorization": "Bearer fake-token"},
        )

    return _get


@pytest_asyncio.fixture
def get_dashboard_asset_data(api_client):
    """GET dashboard asset data helper."""

    async def _get(asset_uuid: str):
        return await api_client.get(
            f"/dashboard/assets/{asset_uuid}/data",
            headers={"Authorization": "Bearer fake-token"},
        )

    return _get


# ─── Seed Data Helpers ─────────────────────────────────────────


@pytest.fixture
def canonical_asset_tree_payload():
    """Canonical asset hierarchy payload."""
    return [
        {
            "id": "ONT",
            "name": "Ontario",
            "type": "system",
            "capacity_kw": 0.0,
            "measured": False,
            "assets": [
                {
                    "id": "K0A",
                    "name": "K0A",
                    "type": "distribution_substation",
                    "capacity_kw": 80000.0,
                    "measured": False,
                    "assets": [],
                },
                {
                    "id": "K0B",
                    "name": "K0B",
                    "type": "distribution_substation",
                    "capacity_kw": 70000.0,
                    "measured": True,
                    "assets": [],
                },
            ],
        }
    ]


@pytest_asyncio.fixture
async def seed_prediction_job(test_session):
    """Create a prediction job row."""

    async def _seed(
        *,
        asset_uuid: str,
        model: str = "xgb",
        horizon_minutes: int = 60,
        frequency_minutes: int = 15,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        config: dict | None = None,
    ) -> PredictionJob:
        pj = PredictionJob(
            asset_uuid=asset_uuid,
            model=model,
            horizon_minutes=horizon_minutes,
            frequency_minutes=frequency_minutes,
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=updated_at or datetime.now(timezone.utc),
            config=config or {},
        )
        test_session.add(pj)
        await test_session.commit()
        await test_session.refresh(pj)
        return pj

    return _seed


@pytest_asyncio.fixture
async def seed_forecast_run(test_session):
    """Create a forecast run row."""

    async def _seed(
        *,
        asset_uuid: str,
        prediction_job_id: int,
        model_run_id: str | None = None,
        created_at: datetime | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        frequency_min: int = 15,
        forecast_run_id: str | None = None,
    ) -> ForecastRun:
        fr = ForecastRun(
            forecast_run_id=forecast_run_id or f"fr_{uuid.uuid4().hex[:10]}",
            prediction_job_id=prediction_job_id,
            model_run_id=model_run_id,
            asset_uuid=asset_uuid,
            created_at=created_at or datetime.now(timezone.utc),
            start_time=start_time,
            end_time=end_time,
            frequency_min=frequency_min,
        )
        test_session.add(fr)
        await test_session.commit()
        await test_session.refresh(fr)
        return fr

    return _seed


@pytest_asyncio.fixture
async def seed_forecast_points(test_session):
    """Create forecast point rows."""

    async def _seed(
        *,
        forecast_run_id: str,
        timestamps: list[datetime],
        values_kw: list[float],
    ) -> list[Forecast]:
        rows = [
            Forecast(
                forecast_run_id=forecast_run_id,
                timestamp=ts,
                forecast_value=float(val),
            )
            for ts, val in zip(timestamps, values_kw)
        ]
        test_session.add_all(rows)
        await test_session.commit()
        return rows

    return _seed


@pytest_asyncio.fixture
async def seed_measurements_load(test_session):
    """Create load measurement rows."""

    async def _seed(
        *,
        asset_uuid: str,
        timestamps: list[datetime],
        load_kw: list[float],
    ) -> list[Measurement]:
        rows = [
            Measurement(
                asset_uuid=asset_uuid,
                timestamp=ts,
                metric="load",
                value=float(val),
            )
            for ts, val in zip(timestamps, load_kw)
        ]
        test_session.add_all(rows)
        await test_session.commit()
        return rows

    return _seed


@pytest_asyncio.fixture
async def seed_forecast_errors(test_session):
    """Create forecast error rows."""

    async def _seed(
        *,
        forecast_run_id: str,
        timestamps: list[datetime],
        errors: list[float],
    ) -> list[ForecastError]:
        rows = [
            ForecastError(
                forecast_run_id=forecast_run_id,
                timestamp=ts,
                error=float(err),
            )
            for ts, err in zip(timestamps, errors)
        ]
        test_session.add_all(rows)
        await test_session.commit()
        return rows

    return _seed
