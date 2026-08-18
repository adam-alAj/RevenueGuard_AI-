"""Tests for configuration validation — secrets must be required outside test mode."""

import os

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_loads_in_test_mode() -> None:
    """Settings should load successfully in test mode with placeholder secrets."""
    os.environ["APP_ENV"] = "testing"
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ.pop("JWT_SECRET", None)

    settings = Settings()
    assert settings.APP_ENV == "testing"
    assert settings.GEMINI_API_KEY == "test-secret-placeholder"
    assert settings.JWT_SECRET == "test-secret-placeholder"


def test_settings_requires_gemini_api_key_in_production() -> None:
    """GEMINI_API_KEY must be set in production — missing value should raise."""
    os.environ["APP_ENV"] = "production"
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ.pop("JWT_SECRET", None)

    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        Settings()


def test_settings_requires_jwt_secret_in_production() -> None:
    """JWT_SECRET must be set in production — missing value should raise."""
    os.environ["APP_ENV"] = "production"
    os.environ["GEMINI_API_KEY"] = "real-key"
    os.environ.pop("JWT_SECRET", None)

    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings()


def test_settings_accepts_provided_secrets_in_production() -> None:
    """Settings should accept explicitly provided secrets in production."""
    os.environ["APP_ENV"] = "production"
    os.environ["GEMINI_API_KEY"] = "real-gemini-key"
    os.environ["JWT_SECRET"] = "real-jwt-secret"

    settings = Settings()
    assert settings.GEMINI_API_KEY == "real-gemini-key"
    assert settings.JWT_SECRET == "real-jwt-secret"
