"""Automated tests for the municipal rules endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

SUPPORTED_CITIES = ["berkeley", "san-francisco", "oakland", "san-jose", "sunnyvale"]
EXPECTED_CATEGORIES = {"compost", "plastic", "paper", "glass", "landfill"}


@pytest.mark.parametrize("city", SUPPORTED_CITIES)
def test_supported_cities_return_200(city: str):
    """Each supported city returns 200 with rules and an official HTTPS source."""
    response = client.get(f"/api/rules/{city}")
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == city
    assert "rules" in data
    assert data["source_url"].startswith("https://")


@pytest.mark.parametrize("city", SUPPORTED_CITIES)
def test_every_city_covers_all_categories(city: str):
    """Each city must have a rule for every category the app classifies."""
    data = client.get(f"/api/rules/{city}").json()
    assert EXPECTED_CATEGORIES <= set(data["rules"])


@pytest.mark.parametrize(
    "spelling", ["San Francisco", "san-francisco", "SAN_FRANCISCO"]
)
def test_city_name_spellings_are_normalized(spelling: str):
    """Different spellings of the same city all resolve to the same key."""
    response = client.get(f"/api/rules/{spelling}")
    assert response.status_code == 200
    assert response.json()["city"] == "san-francisco"


def test_unknown_city_returns_404_with_suggestions():
    """An unknown city gets a 404 that lists the supported cities."""
    response = client.get("/api/rules/unknown_village")
    assert response.status_code == 404
    detail = response.json()["detail"]
    for city in SUPPORTED_CITIES:
        assert city in detail


def test_rules_index_lists_all_supported_cities():
    """GET /api/rules lists every supported city."""
    response = client.get("/api/rules")
    assert response.status_code == 200
    assert set(SUPPORTED_CITIES) <= set(response.json()["supported_cities"])
