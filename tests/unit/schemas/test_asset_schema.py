"""Tests for the AssetIn Pydantic schema in app.schemas."""

import pytest
from forecasting_db.models import AssetType
from pydantic import ValidationError

from app.schemas import AssetIn


def test_asset_in_rejects_extra_fields():
    """Ensure AssetIn raises ValidationError when extra fields are passed."""
    payload = {
        "id": "uuid1",
        "name": "Test Asset",
        "type": AssetType.system,
        "capacity_kW": 100,  # ❌ typo
    }

    with pytest.raises(ValidationError) as exc:
        AssetIn(**payload)

    errors = exc.value.errors()
    assert errors[0]["type"] == "value_error.extra"
    assert errors[0]["loc"] == ("capacity_kW",)


def test_asset_in_assets_not_shared_between_instances():
    """Ensure that nested AssetIn lists are not shared between instances."""
    a1 = AssetIn(
        id="uuid1",
        name="Root A",
        type=AssetType.system,
    )

    a2 = AssetIn(
        id="uuid2",
        name="Root B",
        type=AssetType.system,
    )

    a1.assets.append(
        AssetIn(
            id="child1",
            name="Child",
            type=AssetType.distribution_substation,
        )
    )

    assert len(a1.assets) == 1
    assert a2.assets == []
