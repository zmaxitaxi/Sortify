"""Modular router endpoint unit tests."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app

client = TestClient(app)

AUTH_HEADERS = {"Authorization": "Bearer test-valid-token"}


def test_classify_endpoint_success():
    fake_image = io.BytesIO()
    Image.new("RGB", (16, 16), "green").save(fake_image, format="JPEG")
    fake_image.seek(0)
    response = client.post(
        "/api/classify",
        files={"file": ("sample.jpg", fake_image, "image/jpeg")},
        params={"location": "berkeley"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "compost"
    assert data["bin_color"] == "Green"
    assert "bin" in data
    assert "disposal_tips" in data
    assert len(data["alternatives"]) > 0


def test_classify_endpoint_invalid_file():
    fake_file = io.BytesIO(b"Hello plain text")
    response = client.post(
        "/api/classify",
        files={"file": ("test.txt", fake_file, "text/plain")},
    )
    assert response.status_code == 415
    assert "Unsupported media type" in response.json()["detail"]


def test_classify_endpoint_oversized_file():
    # 1. Create a fake file that starts with JPEG magic bytes so it passes the Type Check
    # JPEG Magic Bytes: \xff\xd8\xff
    header = b"\xff\xd8\xff"
    # Create 11MB of data: Header + junk
    oversized_data = header + b"0" * (11 * 1024 * 1024)
    fake_large_file = io.BytesIO(oversized_data)

    response = client.post(
        "/api/classify",
        files={"file": ("huge_image.jpg", fake_large_file, "image/jpeg")},
    )
    assert response.status_code == 413


def test_rules_endpoint_get_city():
    response = client.get("/api/rules/berkeley")
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "berkeley"
    assert "compost" in data["rules"]
    assert "source_url" in data


def test_rules_endpoint_not_found():
    response = client.get("/api/rules/nonexistent-city")
    assert response.status_code == 404
    assert "Supported cities" in response.json()["detail"]


def test_rules_endpoint_get_all():
    response = client.get("/api/rules")
    assert response.status_code == 200
    data = response.json()
    assert "supported_cities" in data
    assert "berkeley" in data["supported_cities"]


def test_auth_me_endpoint_success():
    response = client.get("/api/auth/me", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "uid" in data
    assert "email" in data
    assert "current_streak" in data


def test_auth_me_endpoint_unauthorized():
    # Missing authorization header
    response = client.get("/api/auth/me")
    assert response.status_code == 401

    # Malformed authorization header
    bad_resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
    assert bad_resp.status_code == 401


def test_auth_verify_endpoint():
    # Valid auth header
    response = client.post(
        "/api/auth/verify",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True

    # Missing auth header
    bad_resp = client.post("/api/auth/verify")
    assert bad_resp.status_code == 401


def test_history_get_endpoint_success():
    response = client.get(
        "/api/history",
        params={"user_id": "d993af39-f604-4426-abf7-fdd664918d15", "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert "scans" in data
    assert data["limit"] == 10
    assert "next_cursor" in data


def test_history_get_requires_guest_uuid():
    response = client.get("/api/history?limit=10")
    assert response.status_code == 422


def test_history_post_endpoint_success():
    payload = {
        "scan_id": "e60685c7-5dcc-42f0-9dc4-176b9676fec7",
        "user_id": "d993af39-f604-4426-abf7-fdd664918d15",
        "timestamp": "2026-10-07T12:00:00Z",
        "category": "paper",
        "item_name": "Cardboard Box",
        "confidence": 0.95,
        "location": "berkeley",
    }
    response = client.post("/api/history", json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "created"
    assert response.json()["scan_id"] == payload["scan_id"]


def test_history_post_rejects_invalid_guest_identifiers():
    payload = {
        "scan_id": "scan-unit-test-2",
        "user_id": "user-test",
        "timestamp": "2026-10-07T12:00:00Z",
        "category": "paper",
        "item_name": "Cardboard Box",
        "confidence": 0.95,
        "location": "berkeley",
    }
    response = client.post("/api/history", json=payload)
    assert response.status_code == 422


def test_cors_headers():
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:19006"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in (
        "http://localhost:19006",
        "*",
    )
