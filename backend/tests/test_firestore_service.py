"""Week 3 Firestore service behavior against an in-memory client."""

from datetime import UTC, datetime

import pytest

from backend.app.services.firestore_service import (
    FirestoreService,
    FirestoreServiceError,
)
from backend.tests.fake_firestore import BoomDB, FakeDB


def test_save_scan_then_read_newest_first():
    service = FirestoreService(FakeDB())
    older = service.save_scan(
        "user-1",
        {
            "predicted_category": "paper",
            "item_name": "Newspaper",
            "confidence": 0.8,
            "timestamp": "2026-10-14T00:00:00+00:00",
        },
    )
    newer = service.save_scan(
        "user-1",
        {
            "category": "plastic",
            "item_name": "Bottle",
            "confidence": 0.5,
            "timestamp": "2026-10-15T00:00:00+00:00",
        },
    )
    service.save_scan(
        "user-2",
        {
            "predicted_category": "glass",
            "item_name": "Jar",
            "confidence": 0.7,
            "timestamp": "2026-10-15T08:00:00+00:00",
        },
    )

    scans = service.get_user_scans("user-1")
    assert [row["scan_id"] for row in scans] == [newer, older]
    assert scans[0]["predicted_category"] == "plastic"
    assert scans[0]["user_id"] == "user-1"
    assert older != newer


def test_get_user_scans_respects_limit_and_rejects_unbounded_reads():
    service = FirestoreService(FakeDB())
    for hour in range(3):
        service.save_scan(
            "user-1",
            {
                "predicted_category": "compost",
                "item_name": f"scrap-{hour}",
                "confidence": 0.4,
                "timestamp": f"2026-10-15T0{hour}:00:00+00:00",
            },
        )
    limited = service.get_user_scans("user-1", limit=2)
    assert len(limited) == 2
    assert limited[0]["item_name"] == "scrap-2"
    with pytest.raises(ValueError, match="limit"):
        service.get_user_scans("user-1", limit=0)
    with pytest.raises(ValueError, match="limit"):
        service.get_user_scans("user-1", limit=101)


def test_save_scan_rejects_invalid_payload_without_writing():
    db = FakeDB()
    service = FirestoreService(db)
    with pytest.raises(ValueError, match="user_id"):
        service.save_scan("  ", {"predicted_category": "paper"})
    with pytest.raises(ValueError, match="Invalid category"):
        service.save_scan("user-1", {"predicted_category": "metal", "confidence": 0.2})
    with pytest.raises(ValueError, match="confidence"):
        service.save_scan(
            "user-1",
            {"predicted_category": "paper", "confidence": 2},
        )
    assert db.docs == {}


def test_save_scan_accepts_datetime_timestamp():
    service = FirestoreService(FakeDB())
    scan_id = service.save_scan(
        "user-1",
        {
            "predicted_category": "landfill",
            "item_name": "Chip bag",
            "confidence": 1,
            "timestamp": datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        },
    )
    stored = service.get_user_scans("user-1")
    assert stored[0]["scan_id"] == scan_id
    assert stored[0]["timestamp"].startswith("2026-10-15T12:00:00")


def test_stats_count_every_scan_when_the_page_is_smaller():
    service = FirestoreService(FakeDB())
    for hour in range(3):
        service.save_scan(
            "user-1",
            {
                "predicted_category": "paper",
                "item_name": f"sheet-{hour}",
                "confidence": 0.4,
                "timestamp": f"2026-10-15T0{hour}:00:00+00:00",
            },
        )
    assert len(service.get_user_scans("user-1", limit=1)) == 1
    assert service.get_user_stats("user-1")["total_scans"] == 3


def test_get_user_stats_for_missing_user_is_zero():
    service = FirestoreService(FakeDB())
    stats = service.get_user_stats("nobody")
    assert stats == {
        "user_id": "nobody",
        "total_scans": 0,
        "current_streak": 0,
        "points": 0,
    }


def test_get_user_stats_counts_scans_and_clamps_bad_counters():
    db = FakeDB()
    service = FirestoreService(db)
    db.collection("users").document("user-1").set(
        {"current_streak": -3, "points": "lots", "total_scans": 99}
    )
    service.save_scan(
        "user-1",
        {"predicted_category": "glass", "item_name": "Jar", "confidence": 0.66},
    )
    stats = service.get_user_stats("user-1")
    assert stats["total_scans"] == 1
    assert stats["current_streak"] == 0
    assert stats["points"] == 0


def test_firestore_outage_is_wrapped_and_does_not_leak_runtime_error():
    service = FirestoreService(BoomDB())
    with pytest.raises(FirestoreServiceError, match="save scan"):
        service.save_scan(
            "user-1",
            {"predicted_category": "paper", "item_name": "Box", "confidence": 0.4},
        )
    with pytest.raises(FirestoreServiceError, match="read scans"):
        service.get_user_scans("user-1")
    with pytest.raises(FirestoreServiceError, match="user stats"):
        service.get_user_stats("user-1")
