"""Week 5 request log: method, path, client, status, and elapsed milliseconds."""

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.middleware.telemetry import TelemetryMiddleware

client = TestClient(app)


def test_health_request_is_logged_with_plan_format(caplog):
    with caplog.at_level(logging.INFO, logger="sortify.api"):
        response = client.get("/health", params={"probe": "1"})
    assert response.status_code == 200
    matches = [
        line
        for line in caplog.messages
        if line.startswith("[GET] /health?probe=1 - testclient - 200 - ")
        and line.endswith("ms")
    ]
    assert len(matches) == 1
    elapsed = matches[0].rsplit(" - ", 1)[-1].removesuffix("ms")
    assert float(elapsed) >= 0


def test_failed_request_logs_500_and_still_raises():
    tiny = FastAPI()
    tiny.add_middleware(TelemetryMiddleware)

    @tiny.get("/boom")
    def boom():
        raise RuntimeError("nope")

    probe = TestClient(tiny, raise_server_exceptions=False)
    records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = ListHandler()
    logger = logging.getLogger("sortify.api")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        response = probe.get("/boom")
    finally:
        logger.removeHandler(handler)
    assert response.status_code == 500
    assert any(line.startswith("[GET] /boom - testclient - 500 - ") for line in records)


def test_log_sink_failure_does_not_change_the_response(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("log sink down")

    monkeypatch.setattr(
        "backend.app.middleware.telemetry.logger.info",
        explode,
    )
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
