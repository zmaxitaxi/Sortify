"""Exercise public errors, private failures, and recovery through HTTP."""

import logging

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.core.exceptions import (
    INTERNAL_MESSAGE,
    EntityNotFoundError,
    InvalidImageError,
    ModelInferenceError,
    PayloadTooLargeError,
    SortifyException,
    register_exception_handlers,
)
from backend.app.main import app
from backend.app.middleware.telemetry import TelemetryMiddleware


@pytest.mark.parametrize(
    "error,status,code",
    [
        (SortifyException("Public message"), 400, "BAD_REQUEST"),
        (InvalidImageError(), 415, "INVALID_IMAGE_FORMAT"),
        (PayloadTooLargeError(), 413, "PAYLOAD_TOO_LARGE"),
        (ModelInferenceError(), 500, "MODEL_INFERENCE_ERROR"),
        (EntityNotFoundError(), 404, "ENTITY_NOT_FOUND"),
    ],
)
def test_domain_errors_return_public_json(error, status, code):
    api = FastAPI()
    register_exception_handlers(api)

    @api.get("/failure")
    def failure():
        raise error

    response = TestClient(api).get("/failure")
    assert response.status_code == status
    assert response.json() == {"error": True, "code": code, "message": error.message}


@pytest.mark.parametrize("source", ["route", "dependency", "middleware"])
def test_unhandled_failures_are_logged_privately_and_server_recovers(source, caplog):
    api = FastAPI()
    register_exception_handlers(api)
    api.add_middleware(TelemetryMiddleware)

    def fail():
        raise RuntimeError("private credential /srv/secret.py")

    if source == "middleware":

        @api.middleware("http")
        async def middleware(request, call_next):
            if request.url.path == "/failure":
                fail()
            return await call_next(request)

    @api.get("/failure", dependencies=[Depends(fail)] if source == "dependency" else [])
    def failure():
        fail()

    @api.get("/health")
    def health():
        return {"status": "ok"}

    with TestClient(api, raise_server_exceptions=False) as client:
        with caplog.at_level(logging.ERROR, logger="backend.app.core.exceptions"):
            response = client.get("/failure")
        assert response.status_code == 500
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {
            "error": True,
            "code": "INTERNAL_SERVER_ERROR",
            "message": INTERNAL_MESSAGE,
        }
        assert client.get("/health").json() == {"status": "ok"}
    assert any(record.exc_info for record in caplog.records)
    assert "private credential" in caplog.text
    assert "private credential" not in response.text


@pytest.mark.parametrize("status", [500, 503, 504])
def test_http_server_errors_hide_internal_detail_and_preserve_headers(status):
    api = FastAPI()
    register_exception_handlers(api)

    @api.get("/failure")
    def failure():
        raise HTTPException(
            status, "private database password", headers={"Retry-After": "1"}
        )

    response = TestClient(api).get("/failure")
    assert response.status_code == status
    assert response.headers["retry-after"] == "1"
    assert response.json()["error"] is True
    assert "password" not in response.text


def test_validation_and_missing_routes_use_safe_envelope():
    client = TestClient(app)
    for response, status, code in [
        (client.get("/api/history?user_id=private-input"), 422, "VALIDATION_ERROR"),
        (
            client.post("/api/history", content=b"{broken private-input"),
            422,
            "VALIDATION_ERROR",
        ),
        (client.get("/missing"), 404, "ENTITY_NOT_FOUND"),
        (client.get("/api/rules/unknown"), 404, "ENTITY_NOT_FOUND"),
    ]:
        assert response.status_code == status
        assert set(response.json()) == {"error", "code", "message"}
        assert response.json()["code"] == code
        assert "private-input" not in response.text


@pytest.mark.parametrize(
    "payload,mime,status,code",
    [
        (b"text", "text/plain", 415, "INVALID_IMAGE_FORMAT"),
        (b"\xff\xd8\xffcorrupt", "image/jpeg", 415, "INVALID_IMAGE_FORMAT"),
        (
            b"\xff\xd8\xff" + b"0" * (11 * 1024 * 1024),
            "image/jpeg",
            413,
            "PAYLOAD_TOO_LARGE",
        ),
    ],
)
def test_bad_uploads_return_uniform_errors_and_health_stays_available(
    payload, mime, status, code
):
    with TestClient(app) as client:
        response = client.post(
            "/api/classify", files={"file": ("photo.jpg", payload, mime)}
        )
        assert response.status_code == status
        assert response.json()["code"] == code
        assert set(response.json()) == {"error", "code", "message"}
        assert client.get("/health").status_code == 200


def test_malformed_multipart_is_a_clean_client_error():
    response = TestClient(app).post(
        "/api/classify",
        content=b"not multipart",
        headers={"content-type": "multipart/form-data"},
    )
    assert response.status_code == 400
    assert response.json() == {
        "error": True,
        "code": "BAD_REQUEST",
        "message": "Missing boundary in multipart.",
    }


def test_openapi_describes_the_actual_error_contract():
    schema = TestClient(app).get("/openapi.json").json()
    response = schema["paths"]["/api/history"]["get"]["responses"]["422"]
    assert response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    assert set(schema["components"]["schemas"]["ErrorResponse"]["properties"]) == {
        "error",
        "code",
        "message",
    }
