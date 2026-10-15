"""Week 4 disposal tips, including the classify response that uses them."""

import io

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.tips_service import (
    TipsDataError,
    get_disposal_guidance,
    get_disposal_tip,
    load_tips,
)

client = TestClient(app)


def test_short_item_keys_do_not_match_inside_other_words():
    cupboard = get_disposal_guidance("plastic", "plastic cupboard")
    bottleneck = get_disposal_guidance("glass", "bottleneck shard")
    assert cupboard["item_tip"] is None
    assert bottleneck["item_tip"] is None


def test_required_category_tips_match_the_week_4_copy():
    expected = {
        "plastic": "Empty liquids and rinse before recycling. Keep caps on.",
        "compost": "Food scraps, soiled napkins, and BPI-certified compostable packaging only.",
        "paper": "Keep clean and dry. Flatten cardboard boxes.",
        "glass": "Rinse jar clean. Metal lids should be separated.",
        "landfill": "Wrappers, chip bags, and styrofoam cannot be recycled.",
    }
    for category, phrase in expected.items():
        assert get_disposal_tip(category) == phrase


def test_item_subtips_differ_for_bottle_cup_and_food_container():
    bottle = get_disposal_tip("plastic", "Plastic Water Bottle")
    cup = get_disposal_tip("plastic", "Iced coffee cup")
    container = get_disposal_tip("plastic", "Takeout food container")
    assert "cap back on" in bottle
    assert "compostable cups" in cup
    assert "rigid plastic" in container
    assert bottle != cup != container


def test_unknown_category_falls_back_to_landfill_without_raising():
    guidance = get_disposal_guidance("metal", "soda can")
    assert guidance["category"] == "landfill"
    assert "cannot be recycled" in guidance["tip"]
    assert get_disposal_tip("  ", "") == get_disposal_tip("landfill", "")


def test_unknown_item_keeps_the_category_tip_only():
    tip = get_disposal_tip("paper", "mystery object")
    assert tip == "Keep clean and dry. Flatten cardboard boxes."
    assert get_disposal_guidance("paper", "mystery object")["item_tip"] is None


def test_location_note_accepts_hyphenated_city_names():
    guidance = get_disposal_guidance("plastic", "bottle", "san-francisco")
    assert guidance["location"] == "san_francisco"
    assert "soft plastics" in guidance["notes"]
    berkeley = get_disposal_guidance("plastic", "bottle", "Berkeley")
    assert "blue cart" in berkeley["notes"]
    assert berkeley["item_tip"] != guidance["notes"]


def test_longest_item_key_wins():
    guidance = get_disposal_guidance("compost", "compostable food container")
    assert "certified compostable" in guidance["item_tip"]
    assert "food-soiled" in guidance["item_tip"]


def test_classify_response_includes_compost_tip_for_the_mock_carton():
    response = client.post(
        "/api/classify",
        files={"file": ("carton.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
        params={"location": "berkeley"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "compost"
    assert body["location"] == "berkeley"
    assert "Empty the carton" in body["disposal_tip"]
    assert "BPI-certified" in body["disposal_tip"]
    assert body["disposal_tips"]["action"] == "Compost"
    assert body["disposal_tips"]["bin_type"] == "green"
    assert "certified compostable" in body["disposal_tips"]["notes"]
    assert "Berkeley organics" in body["disposal_tips"]["notes"]


def test_tips_file_contract_has_all_five_categories():
    categories = load_tips()["categories"]
    assert set(categories) == {"compost", "glass", "landfill", "paper", "plastic"}
    for name, entry in categories.items():
        assert entry["tip"].strip()
        assert entry["action"].strip()
        assert entry["bin_type"].strip()
        assert name


def test_classify_normalizes_hyphenated_locations():
    response = client.post(
        "/api/classify",
        files={"file": ("cup.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
        params={"location": "San-Francisco"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["location"] == "san_francisco"
    assert body["category"] == "compost"


def test_classify_returns_500_when_tips_are_unreadable(monkeypatch):
    def broken(*args, **kwargs):
        raise TipsDataError("tips.json is corrupt")

    monkeypatch.setattr(
        "backend.app.routers.classify.get_disposal_guidance",
        broken,
    )
    response = client.post(
        "/api/classify",
        files={"file": ("cup.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Disposal tips are unavailable."


def test_broken_tips_file_raises(tmp_path, monkeypatch):
    missing = tmp_path / "missing.json"
    monkeypatch.setattr("backend.app.services.tips_service._TIPS_PATH", missing)
    load_tips.cache_clear()
    try:
        with pytest.raises(TipsDataError, match="not found"):
            get_disposal_tip("plastic", "bottle")
    finally:
        load_tips.cache_clear()
