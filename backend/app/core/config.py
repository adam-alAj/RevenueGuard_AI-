"""Application configuration loaded from environment variables.

Secrets (GEMINI_API_KEY, JWT_SECRET) have no default values outside test mode.
The app will refuse to start if they are missing — it will never silently run insecure.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    In production, secrets must be provided via environment variables.
    In test mode (APP_ENV=test), secrets are optional to allow testing
    without real credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "RevenueGuard AI"
    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://revenueguard:revenueguard@localhost:5432/revenueguard"
    )

    # --- Secrets (no defaults outside test mode) ---
    GEMINI_API_KEY: str = ""
    JWT_SECRET: str = ""

    # --- CORS ---
    CORS_ORIGINS: str = ""

    # --- Agent Framework ---
    GEMINI_MODEL: str = "gemini-2.0-flash"

    @field_validator("GEMINI_API_KEY", "JWT_SECRET", mode="before")
    @classmethod
    def _require_secret_outside_test(cls, v: str, info) -> str:
        """Fail fast if a secret is missing outside test mode."""
        if os.getenv("APP_ENV") == "testing":
            # In test mode, allow empty strings (tests don't need real secrets)
            return v or "test-secret-placeholder"
        if not v:
            field_name = info.field_name
            raise ValueError(
                f"{field_name} must be set via environment variable. "
                f"Refusing to start without it — this prevents running insecure."
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton.

    Using lru_cache so the settings are parsed once at startup.
    Call get_settings.cache_clear() in tests to reset between runs.
    """
    return Settings()
