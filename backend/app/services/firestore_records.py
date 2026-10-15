"""Firestore user and scan document contracts.

Runtime scans are stored at ``users/{uid}/scans/{scanId}``. Each scan also
carries ``user_id`` so it matches the flat ``scans/{scanId}`` shape in the
schema doc. ``init_firestore`` seeds both paths.
"""

from datetime import UTC, datetime

from backend.app.schemas.schemas import ALLOWED_CATEGORIES

USER_FIELDS = (
    "email",
    "display_name",
    "created_at",
    "current_streak",
    "total_scans",
    "points",
)
SCAN_FIELDS = (
    "user_id",
    "image_url",
    "predicted_category",
    "item_name",
    "confidence",
    "location",
    "timestamp",
)


def _require_mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict")  # noqa: TRY004
    return value


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be a non-negative integer")  # noqa: TRY004
    if value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def validate_user_document(user: dict) -> dict:
    """Return the stored user fields or raise ValueError."""
    raw = _require_mapping(user, "user")
    email = _nonempty_string(raw.get("email"), "email")
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("email must contain a local part and a domain")
    created_at = _nonempty_string(raw.get("created_at"), "created_at")
    return {
        "email": email,
        "display_name": _nonempty_string(raw.get("display_name"), "display_name"),
        "created_at": created_at,
        "current_streak": _nonnegative_int(raw.get("current_streak"), "current_streak"),
        "total_scans": _nonnegative_int(raw.get("total_scans"), "total_scans"),
        "points": _nonnegative_int(raw.get("points"), "points"),
    }


def _category(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("predicted_category is required")  # noqa: TRY004
    category = value.strip().lower()
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(
            f"Invalid category '{value}'. Must be one of {sorted(ALLOWED_CATEGORIES)}"
        )
    return category


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be a number between 0 and 1")  # noqa: TRY004
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return round(confidence, 4)


def _timestamp(value: object) -> str:
    if value is None:
        return datetime.now(UTC).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("timestamp must be a datetime or ISO-8601 string")


def validate_scan_document(scan: dict, *, default_timestamp: bool = False) -> dict:
    """Return the stored scan fields or raise ValueError."""
    raw = _require_mapping(scan, "scan")
    category = _category(raw.get("predicted_category", raw.get("category")))
    item_name = raw.get("item_name")
    if item_name is None or (isinstance(item_name, str) and not item_name.strip()):
        item_name = category
    elif not isinstance(item_name, str):
        raise ValueError("item_name must be a string")
    timestamp = raw.get("timestamp")
    if timestamp is None and not default_timestamp:
        raise ValueError("timestamp is required")
    return {
        "user_id": _nonempty_string(raw.get("user_id"), "user_id"),
        "image_url": "" if raw.get("image_url") is None else str(raw.get("image_url")),
        "predicted_category": category,
        "item_name": str(item_name).strip(),
        "confidence": _confidence(raw.get("confidence", 0.0)),
        "location": _nonempty_string(
            raw.get("location") or "berkeley", "location"
        ).lower(),
        "timestamp": _timestamp(timestamp),
    }


def build_dummy_records() -> dict:
    """Sample user and scan used to verify the collections without live data."""
    user_id = "user-demo"
    scan_id = "scan-demo"
    user = validate_user_document(
        {
            "email": "krish@sortify.local",
            "display_name": "Demo User",
            "created_at": "2026-10-01T00:00:00+00:00",
            "current_streak": 0,
            "total_scans": 1,
            "points": 0,
        }
    )
    scan = validate_scan_document(
        {
            "user_id": user_id,
            "image_url": "",
            "predicted_category": "plastic",
            "item_name": "Water Bottle",
            "confidence": 0.93,
            "location": "berkeley",
            "timestamp": "2026-10-15T12:00:00+00:00",
        }
    )
    return {
        "user_id": user_id,
        "scan_id": scan_id,
        "user": user,
        "scan": scan,
    }


def write_seed_records(db, records: dict | None = None) -> dict:
    """Write the dummy user and scan. ``db`` is a Firestore client or a fake."""
    payload = records or build_dummy_records()
    user_id = _nonempty_string(payload.get("user_id"), "user_id")
    scan_id = _nonempty_string(payload.get("scan_id"), "scan_id")
    user = validate_user_document(payload.get("user"))
    scan = validate_scan_document(payload.get("scan"))
    if scan["user_id"] != user_id:
        raise ValueError("scan.user_id must match user_id")

    db.collection("users").document(user_id).set(user)
    (
        db.collection("users")
        .document(user_id)
        .collection("scans")
        .document(scan_id)
        .set(scan)
    )
    db.collection("scans").document(scan_id).set(scan)
    return {"user_id": user_id, "scan_id": scan_id}
