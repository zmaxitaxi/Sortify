"""Week 1 upload route: validation, streaming, and path safety."""

import asyncio
import io

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from backend.app.main import app
from backend.app.services import uploads
from backend.app.services.uploads import store_image_upload

client = TestClient(app)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOAD_DIR", tmp_path)
    return tmp_path


def test_upload_image_saves_file_and_returns_receipt(upload_dir):
    payload = b"\xff\xd8\xff\xe0fake-jpeg"
    response = client.post(
        "/upload-image",
        files={"file": ("photo.jpg", io.BytesIO(payload), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received"
    assert body["filename"] == "photo.jpg"
    assert body["size_bytes"] == len(payload)
    assert (upload_dir / "photo.jpg").read_bytes() == payload


def test_upload_image_rejects_non_image(upload_dir):
    response = client.post(
        "/upload-image",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 415
    assert "Image required" in response.json()["message"]
    assert list(upload_dir.iterdir()) == []


def test_upload_image_rejects_missing_content_type(upload_dir):
    upload = UploadFile(
        file=io.BytesIO(b"\xff\xd8"),
        filename="photo.bin",
        headers=Headers({}),
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(store_image_upload(upload, dest_dir=upload_dir))
    assert raised.value.status_code == 415
    assert "Image required" in raised.value.detail
    assert list(upload_dir.iterdir()) == []


def test_upload_image_rejects_empty_file(upload_dir):
    response = client.post(
        "/upload-image",
        files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Empty file."
    assert not (upload_dir / "empty.jpg").exists()


def test_upload_image_strips_path_traversal(upload_dir):
    response = client.post(
        "/upload-image",
        files={"file": ("../outside.jpg", io.BytesIO(b"\xff\xd8abc"), "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "outside.jpg"
    assert (upload_dir / "outside.jpg").is_file()
    assert not (upload_dir.parent / "outside.jpg").exists()


def test_upload_image_rejects_oversized_payload(upload_dir, monkeypatch):
    monkeypatch.setattr(uploads, "upload_byte_limit", lambda: 4)
    response = client.post(
        "/upload-image",
        files={"file": ("big.jpg", io.BytesIO(b"12345"), "image/jpeg")},
    )
    assert response.status_code == 413
    assert "Payload too large" in response.json()["message"]
    assert not (upload_dir / "big.jpg").exists()


def test_upload_image_storage_error_is_http_500(upload_dir, monkeypatch):
    def broken_open(self, mode="r", *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(type(upload_dir), "open", broken_open)
    response = client.post(
        "/upload-image",
        files={"file": ("photo.jpg", io.BytesIO(b"\xff\xd8"), "image/jpeg")},
    )
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_SERVER_ERROR"
    assert "disk full" not in response.text


def test_health_and_upload_are_in_openapi():
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/health" in paths
    assert "/upload-image" in paths
    assert "post" in paths["/upload-image"]
