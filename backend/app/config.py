"""Centralized application environment configuration."""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
DEFAULT_MODEL_PATH = BACKEND_DIR / "app" / "models" / "sortify_mvp_v1.pth"


class Settings(BaseSettings):
    """Application configuration settings parsed from environment variables."""

    ENV: str = Field(default="development", description="Runtime environment")
    PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port server listens on (1-65535)",
    )
    PROJECT_NAME: str = Field(
        default="Sortify Backend", description="Project display name"
    )
    API_V1_STR: str = Field(default="/api", description="API route prefix")
    MODEL_PATH: str = Field(
        default=str(DEFAULT_MODEL_PATH),
        description="Path to model weights checkpoint",
    )
    CORS_ORIGINS: list[str] | str = Field(
        default=[
            "http://localhost:19006",
            "http://localhost:8081",
            "http://localhost:3000",
            "http://127.0.0.1:19006",
            "http://127.0.0.1:8081",
            "http://127.0.0.1:3000",
            "*",
        ],
        description="Allowed CORS origin domains",
        validation_alias=AliasChoices("CORS_ORIGINS", "ALLOWED_ORIGINS"),
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10,
        gt=0,
        description="Maximum image upload size in megabytes (must be > 0)",
    )
    FIREBASE_CREDENTIALS_PATH: str = Field(
        default="serviceAccountKey.json",
        description="Path to Firebase credentials service account key",
    )
    INFERENCE_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    HISTORY_STORAGE: Literal["memory", "firestore"] = Field(
        default="memory",
        description="Scan history storage backend ('memory' or 'firestore')",
    )

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=False,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple:
        """Normalize aliases per source so environment values still override dotenv."""

        def normalize(source):
            def read():
                values = source()
                if "ALLOWED_ORIGINS" in values:
                    values.setdefault("CORS_ORIGINS", values.pop("ALLOWED_ORIGINS"))
                return values

            return read

        return tuple(
            normalize(source)
            for source in (
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )
        )

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, value: Any) -> list[str]:
        """Safely parse CORS_ORIGINS from JSON list, comma-separated string, or list."""
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return []
            if val.startswith("[") and val.endswith("]"):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [
                            str(item).strip().strip("'\"")
                            for item in parsed
                            if str(item).strip().strip("'\"")
                        ]
                except json.JSONDecodeError:
                    val = val[1:-1].strip()
            return [
                item.strip().strip("'\"")
                for item in val.split(",")
                if item.strip().strip("'\"")
            ]
        if isinstance(value, (list, tuple, set)):
            return [
                str(item).strip().strip("'\"")
                for item in value
                if str(item).strip().strip("'\"")
            ]
        return []

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        """Alias for backwards compatibility with earlier router middleware."""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [self.CORS_ORIGINS]


settings = Settings()
