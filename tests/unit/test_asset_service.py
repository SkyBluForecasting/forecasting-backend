"""Unit tests for the asset_service module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.asset_service import fetch_assets, upsert_assets


class MockAsset:
    """Mock object representing an AssetIn-like input for upsert_assets."""

    def __init__(
        self,
        id,
        name,
        type,
        capacity_kw,
        measured=False,
        latitude=None,
        longitude=None,
        assets=None,
    ):
        """Initialize a mock API asset."""
        self.id = id
        self.name = name
        self.type = type
        self.capacity_kw = capacity_kw
        self.measured = measured
        self.latitude = latitude
        self.longitude = longitude
        self.assets = assets or []


class MockAssetRow:
    """Mock database row object representing a persisted Asset."""

    def __init__(
        self,
        asset_uuid,
        name,
        asset_type,
        capacity_kw,
        parent_uuid,
        depth,
        measured,
        latitude=None,
        longitude=None,
        weather_site_id=None,
    ):
        """Initiatlize a mock asset returned from DB."""
        self.asset_uuid = asset_uuid
        self.name = name
        self.asset_type = asset_type
        self.capacity_kw = capacity_kw
        self.parent_uuid = parent_uuid
        self.depth = depth
        self.measured = measured
        self.latitude = latitude
        self.longitude = longitude
        self.weather_site_id = weather_site_id


def make_mock_session(rows):
    """Create an AsyncMock session that returns given rows on execute."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows
    mock_session.execute.return_value = mock_result
    return mock_session


@pytest.mark.asyncio
async def test_upsert_assets_inserts_all_new():
    """Test upserting assets inserts all records when none exist in DB."""
    assets = [
        MockAsset(
            "uuid1",
            "System",
            "system",
            0,
            assets=[
                MockAsset("uuid2", "Sub A", "distribution_substation", 100),
                MockAsset("uuid3", "Sub B", "distribution_substation", 200),
            ],
        )
    ]
    session = make_mock_session([])
    result = await upsert_assets(session, assets)
    assert result == {"inserted": 3, "updated": 0, "total": 3}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_assets_mixed_insert_update():
    """Test upserting assets inserts new and updates existing ones."""
    assets = [
        MockAsset("uuid1", "Root", "system", 0),
        MockAsset("uuid2", "Child", "distribution_substation", 100),
    ]
    session = make_mock_session(["uuid1"])
    result = await upsert_assets(session, assets)
    assert result == {"inserted": 1, "updated": 1, "total": 2}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_assets_empty_input():
    """Test upserting an empty asset list returns zero counts."""
    session = make_mock_session([])
    result = await upsert_assets(session, [])
    assert result == {"inserted": 0, "updated": 0, "total": 0}
    assert session.execute.await_count == 2
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_assets_returns_tree():
    """Test fetch_assets returns a nested hierarchical tree of assets."""
    rows = [
        MockAssetRow("uuid1", "System", "system", 0, None, 0, False),
        MockAssetRow("uuid2", "Sub A", "distribution_substation", 100, "uuid1", 1, False),
        MockAssetRow(
            "uuid3",
            "Sub B",
            "distribution_substation",
            200,
            "uuid1",
            1,
            True,
            latitude=1.0,
            longitude=2.0,
            weather_site_id="site_id_1",
        ),
    ]
    session = make_mock_session(rows)
    result = await fetch_assets(session)

    [root] = result
    assert root["asset_uuid"] == "uuid1"

    # Root fields should exist even if None
    assert "latitude" in root and root["latitude"] is None
    assert "longitude" in root and root["longitude"] is None
    assert "weather_site_id" in root and root["weather_site_id"] is None

    children = {c["asset_uuid"] for c in root["children"]}
    assert children == {"uuid2", "uuid3"}

    # Children should also include the keys
    for c in root["children"]:
        assert "latitude" in c
        assert "longitude" in c
        assert "weather_site_id" in c

    child_b = next(c for c in root["children"] if c["asset_uuid"] == "uuid3")
    assert child_b["latitude"] == 1.0
    assert child_b["longitude"] == 2.0
    assert child_b["weather_site_id"] == "site_id_1"


@pytest.mark.asyncio
async def test_fetch_assets_filters_by_uuid():
    """Test fetch_assets returns subtree when filtered by a specific asset UUID."""
    rows = [
        MockAssetRow("uuid1", "Root", "system", 0, None, 0, False),
        MockAssetRow("uuid2", "Child", "distribution_substation", 100, "uuid1", 1, False),
    ]
    session = make_mock_session(rows)

    result = await fetch_assets(session, "uuid1")
    [root] = result
    assert root["asset_uuid"] == "uuid1"
    assert root["children"][0]["asset_uuid"] == "uuid2"

    # Optional fields should exist (typically None)
    assert "latitude" in root
    assert "longitude" in root
    assert "weather_site_id" in root
    assert "latitude" in root["children"][0]
    assert "longitude" in root["children"][0]
    assert "weather_site_id" in root["children"][0]


@pytest.mark.asyncio
async def test_fetch_assets_filters_by_uuid_nested():
    """Test fetch_assets returns subtree when the target is nested deeper."""
    rows = [
        MockAssetRow("uuid1", "Root", "system", 0, None, 0, False),
        MockAssetRow("uuid2", "Child", "distribution_substation", 100, "uuid1", 1, False),
        MockAssetRow("uuid3", "Grandchild", "distribution_substation", 50, "uuid2", 2, False),
    ]
    session = make_mock_session(rows)

    result = await fetch_assets(session, "uuid3")

    assert len(result) == 1
    node = result[0]
    assert node["asset_uuid"] == "uuid3"
    assert node["children"] == []

    # Optional fields should exist (typically None)
    assert "latitude" in node
    assert "longitude" in node
    assert "weather_site_id" in node


@pytest.mark.asyncio
async def test_fetch_assets_filters_by_uuid_not_found():
    """Test fetch_assets returns empty list when the UUID is not in the tree."""
    rows = [
        MockAssetRow("uuid1", "Root", "system", 0, None, 0, False),
        MockAssetRow("uuid2", "Child", "distribution_substation", 100, "uuid1", 1, False),
    ]
    session = make_mock_session(rows)

    result = await fetch_assets(session, "nonexistent_uuid")
    assert result == []
