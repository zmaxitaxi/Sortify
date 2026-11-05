"""Unit tests for backend environment configuration."""

import json

import pytest
from pydantic import ValidationError

from backend.app.config import Settings


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch):
    for name in (*Settings.model_fields, "ALLOWED_ORIGINS"):
        monkeypatch.delenv(name, raising=False)


def test_default_settings():
    """Verify default settings initialization without external .env interference."""
    cfg = Settings(_env_file=None)
    assert cfg.ENV == "development"
    assert cfg.PORT == 8000
    assert cfg.PROJECT_NAME == "Sortify Backend"
    assert cfg.API_V1_STR == "/api"
    assert cfg.MAX_UPLOAD_SIZE_MB == 10
    assert "*" in cfg.CORS_ORIGINS
    assert cfg.ALLOWED_ORIGINS == cfg.CORS_ORIGINS


def test_custom_environment_settings(monkeypatch):
    """Verify overriding configuration through environment variables."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("CORS_ORIGINS", "https://sortify.app,https://admin.sortify.app")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "15")

    cfg = Settings(_env_file=None)
    assert cfg.ENV == "production"
    assert cfg.PORT == 9000
    assert cfg.CORS_ORIGINS == ["https://sortify.app", "https://admin.sortify.app"]
    assert cfg.MAX_UPLOAD_SIZE_MB == 15


def test_json_cors_origins_parsing(monkeypatch):
    """Verify JSON encoded array parsing for CORS_ORIGINS."""
    origins = ["https://custom1.com", "https://custom2.com"]
    monkeypatch.setenv("CORS_ORIGINS", json.dumps(origins))

    cfg = Settings(_env_file=None)
    assert cfg.CORS_ORIGINS == origins


@pytest.mark.parametrize(
    ("raw_input", "expected"),
    [
        ("https://a.com, https://b.com", ["https://a.com", "https://b.com"]),
        ("  https://a.com ,  https://b.com  ", ["https://a.com", "https://b.com"]),
        ("[https://a.com, https://b.com]", ["https://a.com", "https://b.com"]),
        ("['https://a.com', 'https://b.com']", ["https://a.com", "https://b.com"]),
        ("", []),
        ("   ", []),
        ("[]", []),
    ],
)
def test_cors_origins_edge_cases(monkeypatch, raw_input, expected):
    """Verify robust parsing of whitespace, unquoted brackets, and empty origins."""
    monkeypatch.setenv("CORS_ORIGINS", raw_input)
    cfg = Settings(_env_file=None)
    assert cfg.CORS_ORIGINS == expected


def test_cors_origins_sequence_inputs():
    """Verify tuple, set, and unstripped lists passed directly in Python."""
    cfg = Settings(CORS_ORIGINS=("https://a.com", "https://b.com"), _env_file=None)
    assert cfg.CORS_ORIGINS == ["https://a.com", "https://b.com"]

    cfg_unstripped = Settings(
        CORS_ORIGINS=["  https://a.com  ", "", "  "], _env_file=None
    )
    assert cfg_unstripped.CORS_ORIGINS == ["https://a.com"]


def test_validation_bounds():
    """Verify boundary validation on port and upload size."""
    with pytest.raises(ValidationError):
        Settings(MAX_UPLOAD_SIZE_MB=0, _env_file=None)

    with pytest.raises(ValidationError):
        Settings(MAX_UPLOAD_SIZE_MB=-5, _env_file=None)

    with pytest.raises(ValidationError):
        Settings(PORT=0, _env_file=None)

    with pytest.raises(ValidationError):
        Settings(PORT=70000, _env_file=None)


def test_core_config_interoperability():
    """Ensure importing from backend.app.core.config yields compatible settings."""
    from backend.app.config import settings as app_settings
    from backend.app.core.config import settings as core_settings

    assert core_settings.PORT == app_settings.PORT
    assert core_settings.ENV == app_settings.ENV
    assert core_settings.ALLOWED_ORIGINS == app_settings.CORS_ORIGINS


@pytest.mark.parametrize("name", ["CORS_ORIGINS", "ALLOWED_ORIGINS"])
@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_cors_aliases(name, source, monkeypatch, tmp_path):
    value = '["https://only.example"]'
    env_file = tmp_path / ".env"
    if source == "environment":
        monkeypatch.setenv(name, value)
    else:
        env_file.write_text(f"{name}={value}\n", encoding="utf-8")
    cfg = Settings(_env_file=env_file)
    assert cfg.CORS_ORIGINS == cfg.ALLOWED_ORIGINS == ["https://only.example"]


def test_new_cors_name_takes_precedence_within_source(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://new.example"]')
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://old.example"]')
    assert Settings(_env_file=None).ALLOWED_ORIGINS == ["https://new.example"]


@pytest.mark.parametrize(
    ("env_name", "dotenv_name"),
    [("CORS_ORIGINS", "ALLOWED_ORIGINS"), ("ALLOWED_ORIGINS", "CORS_ORIGINS")],
)
def test_cors_environment_overrides_dotenv_alias(
    env_name, dotenv_name, monkeypatch, tmp_path
):
    env_file = tmp_path / ".env"
    env_file.write_text(f'{dotenv_name}=["https://file.example"]\n', encoding="utf-8")
    monkeypatch.setenv(env_name, '["https://env.example"]')
    assert Settings(_env_file=env_file).ALLOWED_ORIGINS == ["https://env.example"]


def test_legacy_cors_setting_restricts_preflight(monkeypatch):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://only.example"]')
    cfg = Settings(_env_file=None)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=cfg.ALLOWED_ORIGINS)
    client = TestClient(app)
    for origin, expected in [
        ("https://only.example", 200),
        ("https://other.example", 400),
    ]:
        response = client.options(
            "/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert response.status_code == expected
        if expected == 400:
            assert "access-control-allow-origin" not in response.headers
