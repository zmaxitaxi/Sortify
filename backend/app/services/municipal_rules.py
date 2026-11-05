"""Municipal waste-sorting rules shared by the rules and classify routers.

The rules live in backend/app/data/rules.json so they can be edited without
touching code. Re-check each city's rules against its source_url before demos.
"""

import json
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "rules.json"

DEFAULT_CITY = "berkeley"


def _load_rules() -> dict[str, dict]:
    """Read rules.json once and check that every city has the fields we need."""
    if not _RULES_PATH.is_file():
        raise FileNotFoundError(f"Municipal rules file not found at {_RULES_PATH}")
    with _RULES_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    for city, entry in data.items():
        if "rules" not in entry or "source_url" not in entry:
            raise ValueError(f"rules.json: '{city}' needs 'rules' and 'source_url'")
    return data


MUNICIPAL_RULES: dict[str, dict] = _load_rules()


def normalize_city(city: str | None) -> str:
    """Normalize user input to canonical city slug."""
    if not city or not isinstance(city, str):
        return ""
    # Map both 'san_francisco' and 'San Francisco' to canonical 'san-francisco'
    return city.strip().lower().replace("_", "-").replace(" ", "-")


def list_cities() -> list[str]:
    return list(MUNICIPAL_RULES)


def get_city(city: str) -> dict | None:
    """Return a city's rules and source URL, or None if the city isn't supported."""
    return MUNICIPAL_RULES.get(normalize_city(city))


def get_category_rule(category: str, city: str) -> str | None:
    """Return the city's rule sentence for one category, or None if there isn't one."""
    city_data = get_city(city)
    if city_data is None:
        return None
    return city_data["rules"].get(category)
