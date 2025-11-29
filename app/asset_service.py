"""Service for inserting or updating assets."""

import logging

from forecasting_db.models import Asset
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .db_client import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def fetch_assets(asset_uuid: str | None = None):
    """
    Fetch asset records from the database.

    Args:
        asset_uuid (str | None): Optional filter to return a single asset.

    Returns:
        List[dict]: List of asset property dicts.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Asset)
        if asset_uuid:
            stmt = stmt.where(Asset.asset_uuid == asset_uuid)

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "asset_uuid": a.asset_uuid,
                "name": a.name,
                "asset_type": a.asset_type,
                "capacity_kw": a.capacity_kw,
                "parent_uuid": a.parent_uuid,
            }
            for a in rows
        ]


async def upsert_assets(assets):
    """
    Bulk insert or update assets in the database.

    Args:
        assets (List[AssetIn]): List of asset objects.

    Returns:
        dict: Counts of inserted, updated, and total records.
    """
    async with AsyncSessionLocal() as session:
        rows = [
            {
                "asset_uuid": a.id,
                "name": a.name,
                "asset_type": a.type,
                "capacity_kw": a.capacity_kw,
                "parent_uuid": None,  # could extend later for hierarchy
            }
            for a in assets
        ]

        stmt = insert(Asset).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["asset_uuid"],
            set_={
                "name": stmt.excluded.name,
                "asset_type": stmt.excluded.asset_type,
                "capacity_kw": stmt.excluded.capacity_kw,
                "parent_uuid": stmt.excluded.parent_uuid,
            },
        )

        result = await session.execute(stmt)
        await session.commit()

        count = result.rowcount or 0
        logger.info(f"Upserted {count} assets")

    return {"inserted": count, "updated": 0, "total": len(rows)}
