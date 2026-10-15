"""Category tips and item-specific sub-tips for disposal guidance."""

import json
from functools import lru_cache
from pathlib import Path

_TIPS_PATH = Path(__file__).resolve().parent.parent / "data" / "tips.json"


class TipsDataError(Exception):
    """Raised when the tips file is missing or does not match the contract."""


@lru_cache(maxsize=1)
def load_tips() -> dict:
    if not _TIPS_PATH.is_file():
        raise TipsDataError(f"Disposal tips file not found at {_TIPS_PATH}")
    with _TIPS_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    categories = data.get("categories")
    if not isinstance(categories, dict) or "landfill" not in categories:
        raise TipsDataError("tips.json must define categories, including landfill")
    return data


def _location_key(location: str | None) -> str:
    if not location or not str(location).strip():
        return "berkeley"
    return str(location).strip().lower().replace("-", " ").replace(" ", "_")


def _match_item(items: dict, item_name: str | None) -> str | None:
    if not item_name or not isinstance(items, dict):
        return None
    haystack = item_name.strip().lower()
    if not haystack:
        return None
    matches = [key for key in items if isinstance(key, str) and key.lower() in haystack]
    if not matches:
        return None
    best = max(matches, key=len)
    tip = items[best]
    return tip if isinstance(tip, str) and tip.strip() else None


def get_disposal_guidance(
    category: str,
    item_name: str = "",
    location: str = "berkeley",
) -> dict:
    """Return the category tip plus an item sub-tip when one matches.

    Unknown categories fall back to landfill instead of raising, so a bad
    model label cannot take down the classify response.
    """
    tips = load_tips()
    categories = tips["categories"]
    key = category.strip().lower() if isinstance(category, str) else ""
    entry = categories.get(key)
    resolved = key
    if not isinstance(entry, dict):
        entry = categories["landfill"]
        resolved = "landfill"

    general = entry.get("tip")
    if not isinstance(general, str) or not general.strip():
        raise TipsDataError(f"Category '{resolved}' is missing a tip")

    item_tip = _match_item(entry.get("items") or {}, item_name)
    loc_key = _location_key(location)
    locations = entry.get("locations") or {}
    location_note = locations.get(loc_key)
    if not isinstance(location_note, str):
        location_note = None

    notes = item_tip or general
    if location_note:
        notes = f"{notes} {location_note}"

    action = entry.get("action") or resolved.capitalize()
    bin_type = entry.get("bin_type") or "gray"
    return {
        "category": resolved,
        "action": action,
        "bin_type": bin_type,
        "tip": general,
        "item_tip": item_tip,
        "notes": notes,
        "location": loc_key,
    }


def get_disposal_tip(
    category: str,
    item_name: str = "",
    location: str = "berkeley",
) -> str:
    """User-facing tip: the category rule, plus the item rule when it matches."""
    guidance = get_disposal_guidance(category, item_name, location)
    if guidance["item_tip"]:
        return f"{guidance['tip']} {guidance['item_tip']}"
    return guidance["tip"]
