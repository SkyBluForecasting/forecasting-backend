"""Integration tests for the /assets APIs."""

import pytest

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
    children = {c["asset_uuid"] for c in ont["children"]}
    assert children == {"K0A", "K0B"}


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
    children = {c["asset_uuid"] for c in asset["children"]}
    assert children == expected_children
