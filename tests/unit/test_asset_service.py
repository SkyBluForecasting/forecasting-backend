"""Unit tests for the asset_service module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.asset_service import fetch_assets, upsert_assets


class MockAsset:
    """Mock object representing an AssetIn-like input for upsert_assets."""

    def __init__(self, id, name, type, capacity_kw, measured=False, assets=None):
        """
        Initialize a mock asset.

        Args:
            id (str): Unique identifier for the asset.
            name (str): Name of the asset.
            type (str): Asset type (e.g., "system", "distribution_substation").
            capacity_kw (float): Asset capacity in kW.
            measured (bool, optional): Whether the asset is measured. Defaults to False.
            assets (List[MockAsset], optional): Nested child assets. Defaults to empty list.
        """
        self.id = id
        self.name = name
        self.type = type
        self.capacity_kw = capacity_kw
        self.measured = measured
        self.assets = assets or []


class MockAssetRow:
    """Mock database row object representing a persisted Asset."""

    def __init__(self, asset_uuid, name, asset_type, capacity_kw, parent_uuid, depth, measured):
        """
        Initialize a mock database asset row.

        Args:
            asset_uuid (str): Unique identifier of the asset.
            name (str): Asset name.
            asset_type (str): Type of asset.
            capacity_kw (float): Capacity in kW.
            parent_uuid (str | None): UUID of the parent asset, if any.
            depth (int): Depth of the asset in hierarchy.
            measured (bool): Whether the asset is measured.
        """
        self.asset_uuid = asset_uuid
        self.name = name
        self.asset_type = asset_type
        self.capacity_kw = capacity_kw
        self.parent_uuid = parent_uuid
        self.depth = depth
        self.measured = measured


def make_mock_session(rows):
    """Create an AsyncMock session that returns given rows on execute.

    Args:
        rows (List[MockAssetRow | str]): Rows to return when the session executes a query.

    Returns:
        AsyncMock: Mock AsyncSession with execute() returning the provided rows.
    """
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
        MockAssetRow("uuid3", "Sub B", "distribution_substation", 200, "uuid1", 1, True),
    ]
    session = make_mock_session(rows)
    result = await fetch_assets(session)
    root = result[0]
    assert root["asset_uuid"] == "uuid1"
    assert {c["asset_uuid"] for c in root["children"]} == {"uuid2", "uuid3"}


@pytest.mark.asyncio
async def test_fetch_assets_filters_by_uuid():
    """Test fetch_assets returns subtree when filtered by a specific asset UUID."""
    rows = [
        MockAssetRow("uuid1", "Root", "system", 0, None, 0, False),
        MockAssetRow("uuid2", "Child", "distribution_substation", 100, "uuid1", 1, False),
    ]
    session = make_mock_session(rows)
    result = await fetch_assets(session, "uuid1")
    root = result[0]
    assert root["asset_uuid"] == "uuid1"
    assert root["children"][0]["asset_uuid"] == "uuid2"


@pytest.mark.asyncio
async def test_fetch_assets_filters_by_uuid_nested():
    """Test fetch_assets returns subtree when the target is nested deeper."""
    rows = [
        MockAssetRow("uuid1", "Root", "system", 0, None, 0, False),
        MockAssetRow("uuid2", "Child", "distribution_substation", 100, "uuid1", 1, False),
        MockAssetRow("uuid3", "Grandchild", "distribution_substation", 50, "uuid2", 2, False),
    ]
    session = make_mock_session(rows)

    # Filter for the grandchild, triggers recursive find_subtree
    result = await fetch_assets(session, "uuid3")

    # The result should be just the subtree starting at uuid3
    assert len(result) == 1
    node = result[0]
    assert node["asset_uuid"] == "uuid3"
    assert node["children"] == []  # No further children


@pytest.mark.asyncio
async def test_fetch_assets_filters_by_uuid_not_found():
    """Test fetch_assets returns empty list when the UUID is not in the tree."""
    rows = [
        MockAssetRow("uuid1", "Root", "system", 0, None, 0, False),
        MockAssetRow("uuid2", "Child", "distribution_substation", 100, "uuid1", 1, False),
    ]
    session = make_mock_session(rows)

    # Filter for a UUID that doesn't exist
    result = await fetch_assets(session, "nonexistent_uuid")

    # Should return empty list because subtree not found
    assert result == []
