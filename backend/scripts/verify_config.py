"""Script to verify environment settings configuration."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.config import settings


def verify_configuration() -> bool:
    """Inspect and validate parsed application settings."""
    print("=== Sortify Backend Configuration Verification ===")
    print(f"ENV: {settings.ENV}")
    print(f"PORT: {settings.PORT}")
    print(f"PROJECT_NAME: {settings.PROJECT_NAME}")
    print(f"API_V1_STR: {settings.API_V1_STR}")
    print(f"MODEL_PATH: {settings.MODEL_PATH}")
    print(f"CORS_ORIGINS: {settings.CORS_ORIGINS}")
    print(f"MAX_UPLOAD_SIZE_MB: {settings.MAX_UPLOAD_SIZE_MB} MB")
    print(f"FIREBASE_CREDENTIALS_PATH: {settings.FIREBASE_CREDENTIALS_PATH}")

    assert isinstance(settings.ENV, str), "ENV must be a string"
    assert isinstance(settings.PORT, int), "PORT must be an integer"
    assert 1 <= settings.PORT <= 65535, "PORT must be between 1 and 65535"
    assert isinstance(settings.CORS_ORIGINS, list), "CORS_ORIGINS must be a list"
    assert isinstance(settings.MAX_UPLOAD_SIZE_MB, int), (
        "MAX_UPLOAD_SIZE_MB must be an integer"
    )
    assert settings.MAX_UPLOAD_SIZE_MB > 0, "MAX_UPLOAD_SIZE_MB must be greater than 0"
    print("Configuration verification passed successfully!")
    return True


if __name__ == "__main__":
    verify_configuration()
