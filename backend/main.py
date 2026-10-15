"""ASGI entrypoint for `uvicorn backend.main:app` and the CI smoke test."""

from backend.app.main import app

__all__ = ["app"]
