"""Guest history journeys and actual Firestore SDK query construction, without network."""

from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore_v1 import Client, DocumentSnapshot
from google.cloud.firestore_v1.document import DocumentReference
from google.cloud.firestore_v1.query import Query

from backend.app.main import app, fastapi_app
from backend.app.routers.history import get_history_service
from backend.app.schemas.schemas import GuestScanRecord
from backend.app.services.history_service import HistoryService, HistoryServiceError
from backend.app.services.history_service import (
    get_history_service as configured_service,
)

DEVICE = UUID("d993af39-f604-4426-abf7-fdd664918d15")


def scan(index=1, user_id=DEVICE, **overrides):
    return {
        "user_id": str(user_id),
        "scan_id": str(UUID(int=index)),
        "item_name": "Bottle",
        "category": "plastic",
        "confidence": 0.95,
        "timestamp": "2026-10-28T08:00:00Z",
        **overrides,
    }


@pytest.fixture
def client():
    service = HistoryService()
    fastapi_app.dependency_overrides[get_history_service] = lambda: service
    with TestClient(app) as client:
        yield client
    fastapi_app.dependency_overrides.pop(get_history_service)


def test_three_posts_two_pages_and_other_device_isolation(client):
    for index in (1, 2, 3):
        response = client.post("/api/history", json=scan(index))
        assert response.status_code == 201
        assert response.json()["scan"]["bin"] == "Blue Plastic Bin"
    client.post("/api/history", json=scan(4, user_id=uuid4()))
    page = client.get(
        "/api/history", params={"user_id": str(DEVICE), "limit": 2}
    ).json()
    assert [row["scan_id"] for row in page["scans"]] == [
        str(UUID(int=3)),
        str(UUID(int=2)),
    ]
    assert page["next_cursor"]
    # A newer insertion must not shift the older page boundary.
    client.post("/api/history", json=scan(5, timestamp="2026-10-28T09:00:00Z"))
    second = client.get(
        "/api/history",
        params={"user_id": str(DEVICE), "limit": 2, "cursor": page["next_cursor"]},
    ).json()
    assert [row["scan_id"] for row in second["scans"]] == [str(UUID(int=1))]
    assert second["next_cursor"] is None
    other = client.get("/api/history", params={"user_id": str(uuid4())}).json()
    assert other["scans"] == [] and other["next_cursor"] is None
    wrong_device = client.get(
        "/api/history", params={"user_id": str(uuid4()), "cursor": page["next_cursor"]}
    )
    assert wrong_device.status_code == 400


def test_generated_ids_utc_normalization_and_idempotent_retry(client):
    payload = scan(timestamp="2026-10-28T01:00:00-07:00")
    payload.pop("scan_id")
    record = client.post("/api/history", json=payload).json()["scan"]
    UUID(record["scan_id"])
    assert record["timestamp"] == "2026-10-28T08:00:00Z"
    assert client.post("/api/history", json=record).status_code == 201
    assert (
        len(client.get("/api/history", params={"user_id": str(DEVICE)}).json()["scans"])
        == 1
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_id", "../bad"),
        ("scan_id", "a/b"),
        ("timestamp", "2026-10-28T01:00:00"),
        ("category", 42),
        ("confidence", 1.1),
    ],
)
def test_invalid_scan_is_422(client, field, value):
    assert client.post("/api/history", json=scan(**{field: value})).status_code == 422


def test_invalid_page_parameters_and_exact_page_end(client):
    for limit in (0, 101):
        assert (
            client.get(
                "/api/history", params={"user_id": str(DEVICE), "limit": limit}
            ).status_code
            == 422
        )
    assert (
        client.get(
            "/api/history", params={"user_id": str(DEVICE), "cursor": "%%%"}
        ).status_code
        == 400
    )
    for index in (1, 2):
        client.post("/api/history", json=scan(index))
    assert (
        client.get("/api/history", params={"user_id": str(DEVICE), "limit": 2}).json()[
            "next_cursor"
        ]
        is None
    )


def test_firestore_paths_timestamp_and_bounded_cursor_query(monkeypatch):
    db = Client(project="sortify-unit", credentials=AnonymousCredentials())
    writes, queries = {}, []

    def save(ref, payload):
        writes[ref.path] = payload

    def stream(query):
        proto = query._to_protobuf()
        queries.append(proto)
        assert [order.field.field_path for order in proto.order_by] == [
            "timestamp",
            "__name__",
        ]
        assert all(order.direction == 2 for order in proto.order_by)
        assert proto.limit == 3
        assert proto.offset == 0
        ids = (3, 2, 1) if len(queries) == 1 else (1,)
        return iter(
            DocumentSnapshot(
                db.document(f"users/{DEVICE}/scans/{UUID(int=i)}"),
                writes[f"users/{DEVICE}/scans/{UUID(int=i)}"],
                True,
                None,
                None,
                None,
            )
            for i in ids
        )

    monkeypatch.setattr(DocumentReference, "set", save)
    monkeypatch.setattr(Query, "stream", stream)
    service = HistoryService(db)
    for index in (1, 2, 3):
        service.save_scan(scan(index))
    assert len(writes) == 3
    assert all(
        row["timestamp"] == datetime(2026, 10, 28, 8, tzinfo=UTC)
        for row in writes.values()
    )
    # A separate service instance sees records saved through the same database.
    reader = HistoryService(db)
    page = reader.get_user_history(DEVICE, limit=2)
    second = reader.get_user_history(DEVICE, limit=2, cursor=page["next_cursor"])
    assert len(page["scans"]) == 2 and len(second["scans"]) == 1
    cursor = queries[1].start_at
    assert not cursor.before
    assert cursor.values[1].reference_value.endswith(
        f"users/{DEVICE}/scans/{UUID(int=2)}"
    )


def test_firestore_failure_never_silently_falls_back(client):
    db = Mock()
    db.collection.side_effect = RuntimeError("private database details")
    service = HistoryService(db)
    with pytest.raises(HistoryServiceError):
        service.save_scan(scan())
    assert service._records == {}
    fastapi_app.dependency_overrides[get_history_service] = lambda: service
    response = client.get("/api/history", params={"user_id": str(DEVICE)})
    assert response.status_code == 503
    assert "private" not in response.text
    assert client.post("/api/history", json=scan()).status_code == 503


def test_memory_mode_does_not_initialize_firebase(monkeypatch):
    from backend.app.services import firebase, history_service

    monkeypatch.setattr(history_service.settings, "HISTORY_STORAGE", "memory")
    connect = Mock(side_effect=RuntimeError("must not connect"))
    monkeypatch.setattr(firebase, "get_db", connect)
    configured_service.cache_clear()
    try:
        assert configured_service().db is None
        connect.assert_not_called()
        configured_service.cache_clear()
        monkeypatch.setattr(history_service.settings, "HISTORY_STORAGE", "firestore")
        with pytest.raises(HistoryServiceError):
            configured_service()
    finally:
        configured_service.cache_clear()


def test_record_defaults_are_complete():
    record = GuestScanRecord(
        user_id=DEVICE, item_name="Paper", category="paper", confidence=1
    )
    assert record.timestamp.tzinfo is not None
    assert record.bin == "Brown Paper Bin"
