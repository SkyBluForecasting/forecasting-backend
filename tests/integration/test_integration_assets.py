"""Integration tests for the /assets APIs."""

import pytest
from forecasting_db.models import Asset, WeatherSite
from sqlalchemy import select, update

from app.asset_service import fetch_assets


@pytest.mark.asyncio
async def test_post_assets_inserts(post_assets, test_session, canonical_asset_tree_payload):
    """POST /assets should insert nested assets correctly."""
    response = await post_assets(canonical_asset_tree_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["inserted"] == 3
    assert data["updated"] == 0
    assert data["total"] == 3

    # Verify in DB
    assets = await fetch_assets(test_session)
    [ont] = assets

    assert ont["asset_uuid"] == "ONT"
    assert "latitude" in ont and ont["latitude"] is None
    assert "weather_site_id" in ont and ont["weather_site_id"] is None
    assert ont["measured"] is False
    assert ont["capacity_kw"] == 0.0
    assert ont["asset_type"] == "system"

    children = {c["asset_uuid"] for c in ont["children"]}
    assert children == {"K0A", "K0B"}
    k0a = next(c for c in ont["children"] if c["asset_uuid"] == "K0A")
    assert k0a["measured"] is False
    assert k0a["capacity_kw"] == 80000.0
    assert k0a["measured"] is False
    assert k0a["latitude"] is None
    assert k0a["longitude"] is None
    assert k0a["weather_site_id"] is None


@pytest.mark.asyncio
async def test_post_assets_updates_existing(post_assets, test_session):
    """POST /assets should update existing assets."""
    # Initial insert
    initial_payload = [
        {
            "id": "ONT",
            "name": "Ontario",
            "type": "system",
            "capacity_kw": 0.0,
            "measured": False,
            "assets": [],
        }
    ]
    await post_assets(initial_payload)

    # Update the asset
    updated_payload = [
        {
            "id": "ONT",
            "name": "Ontario Updated",
            "type": "system",
            "capacity_kw": 10.0,
            "measured": True,
            "assets": [],
        }
    ]
    response = await post_assets(updated_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["inserted"] == 0
    assert data["updated"] == 1
    assert data["total"] == 1

    # Verify DB state
    assets = await fetch_assets(test_session)
    [ont] = assets
    assert ont["name"] == "Ontario Updated"
    assert ont["capacity_kw"] == 10.0
    assert ont["measured"] is True

    assert "latitude" in ont
    assert "weather_site_id" in ont


@pytest.mark.asyncio
async def test_post_assets_clears_weather_site_id_when_coords_change(post_assets, test_session):
    """POST /assets should clear weather_site_id if lat/long changes."""
    # 1) Insert with initial coords
    initial_payload = [
        {
            "id": "ONT",
            "name": "Ontario",
            "type": "system",
            "capacity_kw": 0.0,
            "measured": False,
            "latitude": 43.0,
            "longitude": -79.0,
            "assets": [],
        }
    ]
    resp = await post_assets(initial_payload)
    assert resp.status_code == 200

    # 2) Simulate nightly job mapping weather_site_id
    site = WeatherSite(
        weather_site_id="site_123",
        site_lat=43.0,
        site_long=-79.0,
    )
    test_session.add(site)
    await test_session.commit()

    await test_session.execute(
        update(Asset).where(Asset.asset_uuid == "ONT").values(weather_site_id="site_123")
    )
    await test_session.commit()

    # sanity check (read columns, not ORM object)
    (wsid,) = (
        await test_session.execute(select(Asset.weather_site_id).where(Asset.asset_uuid == "ONT"))
    ).one()
    assert wsid == "site_123"

    # 3) POST with changed coords (should clear weather_site_id)
    updated_payload = [
        {
            "id": "ONT",
            "name": "Ontario",
            "type": "system",
            "capacity_kw": 0.0,
            "measured": False,
            "latitude": 44.0,  # changed
            "longitude": -79.0,  # same
            "assets": [],
        }
    ]
    resp2 = await post_assets(updated_payload)
    assert resp2.status_code == 200

    # Verify DB state (read columns, not ORM object)
    lat2, lon2, wsid2 = (
        await test_session.execute(
            select(Asset.latitude, Asset.longitude, Asset.weather_site_id).where(
                Asset.asset_uuid == "ONT"
            )
        )
    ).one()

    assert lat2 == 44.0
    assert lon2 == -79.0
    assert wsid2 is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params,expected_count,expected_uuid,expected_children",
    [
        (None, 1, "ONT", {"K0A", "K0B"}),  # GET all assets returns all children
        ({"asset_uuid": "ONT"}, 1, "ONT", {"K0A", "K0B"}),  # GET single asset returns same children
    ],
)
async def test_get_assets(
    post_assets,
    get_assets,
    canonical_asset_tree_payload,
    params,
    expected_count,
    expected_uuid,
    expected_children,
):
    """GET /assets returns all or single assets correctly."""
    await post_assets(canonical_asset_tree_payload)

    response = await get_assets(params=params)
    assert response.status_code == 200

    assets = response.json()
    assert len(assets) == expected_count

    [asset] = assets
    assert asset["asset_uuid"] == expected_uuid
    assert "latitude" in asset
    assert "longitude" in asset
    assert "weather_site_id" in asset

    children = {c["asset_uuid"] for c in asset["children"]}
    assert children == expected_children
