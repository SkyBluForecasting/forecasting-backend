"""Service for inserting or updating assets."""

import logging
from typing import List

from forecasting_db.models import Asset, AssetType
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import AssetIn

logger = logging.getLogger(__name__)


def build_tree(flat_assets):
    """
    Convert a flat list of assets into a hierarchical tree structure.

    Args:
        flat_assets (List[dict]): List of asset dicts, each containing at least
            'asset_uuid' and 'parent_uuid' keys.

    Returns:
        List[dict]: Nested list of assets where each asset contains a 'children'
            key with its child assets.
    """
    asset_map = {a["asset_uuid"]: a for a in flat_assets}
    tree = []

    for a in flat_assets:
        a["children"] = []

    for a in flat_assets:
        parent_uuid = a["parent_uuid"]
        if parent_uuid:
            asset_map[parent_uuid]["children"].append(a)
        else:
            tree.append(a)

    return tree


async def fetch_assets(session: AsyncSession, asset_uuid: str | None = None):
    """
    Fetch asset records from the database.

    Args:
        session (AsyncSession): The database session to use.
        asset_uuid (str | None): Optional filter to return a single asset.

    Returns:
        List[dict]: List of asset property dicts.
    """
    stmt = select(Asset)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    flat_assets = [
        {
            "asset_uuid": a.asset_uuid,
            "name": a.name,
            "asset_type": a.asset_type,
            "capacity_kw": getattr(a, "capacity_kw", None),
            "parent_uuid": getattr(a, "parent_uuid", None),
            "depth": a.depth,
            "measured": a.measured,
            "latitude": getattr(a, "latitude", None),
            "longitude": getattr(a, "longitude", None),
            "weather_site_id": getattr(a, "weather_site_id", None),
        }
        for a in rows
    ]

    tree = build_tree(flat_assets)

    if asset_uuid:
        # return just the subtree starting at asset_uuid
        def find_subtree(nodes, target_uuid):
            for node in nodes:
                if node["asset_uuid"] == target_uuid:
                    return node
                res = find_subtree(node.get("children", []), target_uuid)
                if res:
                    return res
            return None

        subtree = find_subtree(tree, asset_uuid)
        return [subtree] if subtree else []

    return tree


async def upsert_assets(session: AsyncSession, assets: List[AssetIn]):
    """
    Bulk insert or update nested assets.

    Args:
        session (AsyncSession): The database session to use.
        assets (List[AssetIn]): List of asset objects in a nested hierarchy.

    Returns:
        dict: Counts of inserted, updated, and total records.
    """
    rows_by_uuid = {}

    def flatten(a_list, parent_uuid=None, depth=0):
        for a in a_list:
            rows_by_uuid[a.id] = {
                "asset_uuid": a.id,
                "name": a.name,
                "asset_type": AssetType[a.type],
                "capacity_kw": a.capacity_kw,
                "measured": a.measured,
                "parent_uuid": parent_uuid,
                "depth": depth,
            }
            if a.assets:
                flatten(a.assets, parent_uuid=a.id, depth=depth + 1)

    flatten(assets)
    flat_rows = list(rows_by_uuid.values())

    # Find existing assets
    result = await session.execute(
        select(Asset.asset_uuid).where(Asset.asset_uuid.in_([r["asset_uuid"] for r in flat_rows]))
    )
    existing_uuids = set(result.scalars().all())

    # Upsert
    stmt = insert(Asset).values(flat_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["asset_uuid"],
        set_={
            "name": stmt.excluded.name,
            "asset_type": stmt.excluded.asset_type,
            "capacity_kw": stmt.excluded.capacity_kw,
            "measured": stmt.excluded.measured,
            "parent_uuid": stmt.excluded.parent_uuid,
            "depth": stmt.excluded.depth,
        },
    )

    await session.execute(stmt)
    await session.commit()

    total = len(flat_rows)
    updated = len(existing_uuids)
    inserted = total - updated

    return {"inserted": inserted, "updated": updated, "total": total}
