"""Week 2 Firestore document contract and seed writer."""

import json
import subprocess
import sys

import pytest

from backend.app.services.firestore_records import (
    SCAN_FIELDS,
    USER_FIELDS,
    build_dummy_records,
    validate_scan_document,
    validate_user_document,
    write_seed_records,
)
from backend.tests.fake_firestore import FakeDB


def test_dummy_records_cover_the_schema_fields():
    records = build_dummy_records()
    assert set(records["user"]) == set(USER_FIELDS)
    assert set(records["scan"]) == set(SCAN_FIELDS)
    assert records["scan"]["user_id"] == records["user_id"]
    assert records["scan"]["predicted_category"] == "plastic"
    assert 0.0 <= records["scan"]["confidence"] <= 1.0


def test_user_document_rejects_bad_email_and_negative_counts():
    base = build_dummy_records()["user"]
    with pytest.raises(ValueError, match="email"):
        validate_user_document({**base, "email": "not-an-email"})
    with pytest.raises(ValueError, match="current_streak"):
        validate_user_document({**base, "current_streak": -1})
    with pytest.raises(ValueError, match="points"):
        validate_user_document({**base, "points": True})


def test_scan_document_rejects_unknown_category_and_confidence():
    base = build_dummy_records()["scan"]
    with pytest.raises(ValueError, match="Invalid category"):
        validate_scan_document({**base, "predicted_category": "metal"})
    with pytest.raises(ValueError, match="confidence"):
        validate_scan_document({**base, "confidence": 1.2})
    with pytest.raises(ValueError, match="timestamp"):
        validate_scan_document({**base, "timestamp": ""})


def test_write_seed_records_hits_user_subcollection_and_flat_scans():
    db = FakeDB()
    written = write_seed_records(db)
    user = db.collection("users").document(written["user_id"]).get()
    assert user.exists
    assert user.to_dict()["email"] == "krish@sortify.local"

    nested = (
        db.collection("users")
        .document(written["user_id"])
        .collection("scans")
        .document(written["scan_id"])
        .get()
    )
    flat = db.collection("scans").document(written["scan_id"]).get()
    assert nested.exists and flat.exists
    assert nested.to_dict() == flat.to_dict()
    assert nested.to_dict()["predicted_category"] == "plastic"


def test_write_seed_records_rejects_mismatched_user_id():
    records = build_dummy_records()
    records["scan"]["user_id"] = "someone-else"
    with pytest.raises(ValueError, match="user_id"):
        write_seed_records(FakeDB(), records)


def test_init_firestore_dry_run_without_credentials():
    completed = subprocess.run(
        [sys.executable, "backend/scripts/init_firestore.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["user"]["current_streak"] == 0
    assert payload["scan"]["item_name"] == "Water Bottle"


def test_init_firestore_live_flag_fails_without_credentials():
    completed = subprocess.run(
        [sys.executable, "backend/scripts/init_firestore.py", "--live"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "credentials" in completed.stderr.lower()
