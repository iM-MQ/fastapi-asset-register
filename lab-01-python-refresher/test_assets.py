"""Tests for assets.py. Run with: python -m pytest"""

import pytest

from assets import (
    Asset,
    Status,
    add_asset,
    count_by_status,
    find_by_tag,
    load_assets,
    save_assets,
)


def make_asset(**changes) -> Asset:
    """A valid asset, with any field overridden for a test."""
    fields = {"tag": "AST-0001", "name": "Test laptop", "category": "laptop"}
    fields.update(changes)
    return Asset(**fields)


def test_new_asset_defaults_to_in_stock():
    asset = make_asset()
    assert asset.status == Status.IN_STOCK
    assert asset.assigned_to is None


def test_tag_is_tidied_up():
    asset = make_asset(tag="  ast-0042 ")
    assert asset.tag == "AST-0042"


@pytest.mark.parametrize("bad_tag", ["0001", "AST-1", "AST-00001", "XYZ-0001", ""])
def test_badly_formed_tags_are_rejected(bad_tag):
    with pytest.raises(ValueError, match="must look like AST-0001"):
        make_asset(tag=bad_tag)


def test_empty_name_is_rejected():
    with pytest.raises(ValueError, match="Name must not be empty"):
        make_asset(name="   ")


def test_unknown_status_is_rejected():
    with pytest.raises(ValueError):
        make_asset(status="lost")


def test_status_text_from_json_becomes_a_status():
    asset = make_asset(status="repair")
    assert asset.status is Status.REPAIR


def test_in_use_asset_must_be_assigned():
    with pytest.raises(ValueError, match="must be assigned"):
        make_asset(status="in_use")


def test_save_then_load_gives_the_same_assets(tmp_path):
    # tmp_path is a fresh, empty folder that pytest creates for this test only
    original = [
        make_asset(),
        make_asset(tag="AST-0002", status="in_use", assigned_to="Reception"),
    ]
    path = tmp_path / "assets.json"

    save_assets(original, path)
    loaded = load_assets(path)

    assert loaded == original


def test_find_by_tag_ignores_case():
    assets = [make_asset(tag="AST-0007")]
    assert find_by_tag(assets, "ast-0007") is assets[0]


def test_find_by_tag_returns_none_when_missing():
    assert find_by_tag([make_asset()], "AST-9999") is None


def test_adding_a_duplicate_tag_is_rejected():
    assets = [make_asset()]
    with pytest.raises(ValueError, match="already in the register"):
        add_asset(assets, make_asset(name="Another laptop"))


def test_add_asset_does_not_change_the_original_list():
    assets = [make_asset()]
    updated = add_asset(assets, make_asset(tag="AST-0002"))
    assert len(assets) == 1
    assert len(updated) == 2


def test_count_by_status():
    assets = [
        make_asset(tag="AST-0001"),
        make_asset(tag="AST-0002"),
        make_asset(tag="AST-0003", status="retired"),
    ]
    assert count_by_status(assets) == {"in_stock": 2, "retired": 1}