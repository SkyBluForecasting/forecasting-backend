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
        """Initialize a mock asset returned from DB."""
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
    """
    Create an AsyncMock session that returns given rows on execute().

    This helper is used for both:
      - upsert_assets (which executes a SELECT then an INSERT ... ON CONFLICT)
      - fetch_assets (which executes a SELECT)
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows
    mock_session.execute.return_value = mock_result
    return mock_session


def _extract_compiled_params_from_upsert_execute(mock_session: AsyncMock) -> dict:
    """
    Extract compiled params from the second execute() call.

    Returns:
        dict: compiled params for the statement
    """
    # 0th call: SELECT existing assets
    # 1st call: INSERT/UPSERT
    assert (
        mock_session.execute.await_count >= 2
    ), "Expected at least 2 execute() calls (select + upsert)."
    upsert_stmt = mock_session.execute.await_args_list[1].args[0]
    return upsert_stmt.compile().params


def _group_rows_from_compiled_params(params: dict) -> list[dict]:
    """
    Sqlalchemy expands insert(values=[...]) into parameters like.

      asset_uuid_m0, name_m0, depth_m0, ...
      asset_uuid_m1, name_m1, depth_m1, ...

    This helper groups those back into per-row dicts keyed by the suffix.
    """
    groups: dict[str, dict] = {}
    for key, val in params.items():
        if "_m" not in key:
            # Some dialects emit params without _m suffix; ignore for now
            continue
        base, suffix = key.rsplit("_m", 1)
        groups.setdefault(suffix, {})[base] = val
    # Return rows in a stable order by numeric suffix
    return [groups[k] for k in sorted(groups.keys(), key=lambda s: int(s) if s.isdigit() else s)]


@pytest.mark.asyncio
async def test_upsert_assets_inserts_all_new_builds_correct_rows_and_counts():
    """Test upserting assets inserts all records when none exist in DB."""
    assets = [
        MockAsset(
            "uuid1",
            "System",
            "system",
            0,
            measured=False,
            assets=[
                MockAsset("uuid2", "Sub A", "distribution_substation", 100, measured=False),
                MockAsset(
                    "uuid3",
                    "Sub B",
                    "distribution_substation",
                    200,
                    measured=True,
                    latitude=1.0,
                    longitude=2.0,
                ),
            ],
        )
    ]
    session = make_mock_session([])

    result = await upsert_assets(session, assets)
    assert result == {"inserted": 3, "updated": 0, "total": 3}
    session.commit.assert_awaited_once()

    # Validate the upsert payload (not just counts)
    params = _extract_compiled_params_from_upsert_execute(session)
    rows = _group_rows_from_compiled_params(params)

    assert len(rows) == 3

    by_uuid = {r["asset_uuid"]: r for r in rows}
    assert set(by_uuid.keys()) == {"uuid1", "uuid2", "uuid3"}

    # Root
    r1 = by_uuid["uuid1"]
    assert r1["name"] == "System"
    assert r1["parent_uuid"] is None
    assert r1["depth"] == 0
    assert r1["capacity_kw"] == 0
    assert r1["measured"] is False
    assert r1.get("latitude") is None
    assert r1.get("longitude") is None

    # Child A
    r2 = by_uuid["uuid2"]
    assert r2["name"] == "Sub A"
    assert r2["parent_uuid"] == "uuid1"
    assert r2["depth"] == 1
    assert r2["capacity_kw"] == 100
    assert r2["measured"] is False

    # Child B (lat/lon provided)
    r3 = by_uuid["uuid3"]
    assert r3["name"] == "Sub B"
    assert r3["parent_uuid"] == "uuid1"
    assert r3["depth"] == 1
    assert r3["capacity_kw"] == 200
    assert r3["measured"] is True
    assert r3.get("latitude") == 1.0
    assert r3.get("longitude") == 2.0

    # Basic check that asset_type is being set (enum or string depending on model)
    assert "asset_type" in r1 and r1["asset_type"] is not None
    assert "asset_type" in r2 and r2["asset_type"] is not None
    assert "asset_type" in r3 and r3["asset_type"] is not None


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
    # upsert_assets always runs two execute() calls even on empty input
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
    assert root["latitude"] is None
    assert root["longitude"] is None
    assert root["weather_site_id"] is None

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
    assert {c["asset_uuid"] for c in root["children"]} == {"uuid2"}

    child = root["children"][0]

    # Optional fields should exist and default to None
    assert root["latitude"] is None
    assert root["longitude"] is None
    assert root["weather_site_id"] is None
    assert child["latitude"] is None
    assert child["longitude"] is None
    assert child["weather_site_id"] is None


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

    # Optional fields should exist and default to None
    assert node["latitude"] is None
    assert node["longitude"] is None
    assert node["weather_site_id"] is None


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
