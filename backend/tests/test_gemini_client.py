"""Tests for the Gemini client wrapper.

All tests mock the actual Gemini API calls — no live API calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agents.gemini_client import (
    GeminiClientError,
    create_default_options,
    create_gemini_client,
)


class TestCreateGeminiClient:
    """Tests for create_gemini_client factory function."""

    def test_creates_client_with_valid_key(self) -> None:
        """Valid API key produces a GeminiChatClient."""
        client = create_gemini_client(api_key="test-key-123")
        assert client is not None

    def test_creates_client_with_custom_model(self) -> None:
        """Custom model parameter is accepted."""
        client = create_gemini_client(
            api_key="test-key-123",
            model="gemini-2.5-pro",
        )
        assert client is not None

    def test_raises_error_when_api_key_empty(self) -> None:
        """Empty API key raises GeminiClientError."""
        with pytest.raises(GeminiClientError, match="GEMINI_API_KEY is required"):
            create_gemini_client(api_key="")

    def test_raises_error_when_api_key_none(self) -> None:
        """None API key raises GeminiClientError."""
        with pytest.raises(GeminiClientError, match="GEMINI_API_KEY is required"):
            create_gemini_client(api_key=None)  # type: ignore[arg-type]

    def test_error_message_is_human_readable(self) -> None:
        """Error message provides clear guidance."""
        with pytest.raises(GeminiClientError) as exc_info:
            create_gemini_client(api_key="")
        assert "environment variable" in str(exc_info.value).lower()


class TestCreateDefaultOptions:
    """Tests for create_default_options factory."""

    def test_default_temperature(self) -> None:
        """Default temperature is 0.7."""
        opts = create_default_options()
        assert opts["temperature"] == 0.7

    def test_custom_temperature(self) -> None:
        """Custom temperature is respected."""
        opts = create_default_options(temperature=0.2)
        assert opts["temperature"] == 0.2

    def test_returns_dict(self) -> None:
        """Options are a dict (GeminiChatOptions is a dict subclass)."""
        opts = create_default_options()
        assert isinstance(opts, dict)


class TestGeminiClientIntegration:
    """Tests that verify the client works with the Agent framework (mocked)."""

    @patch("app.agents.gemini_client.GeminiChatClient")
    def test_client_can_be_used_with_agent(self, mock_client_cls: MagicMock) -> None:
        """GeminiChatClient can be passed to Agent constructor."""
        from agent_framework import Agent

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = create_gemini_client(api_key="test-key")
        agent = Agent(
            client=client,
            instructions="Test agent",
            name="test-agent",
        )
        assert agent is not None

    def test_gemini_client_is_not_none(self) -> None:
        """Client is a real GeminiChatClient instance."""
        from agent_framework_gemini import GeminiChatClient

        client = create_gemini_client(api_key="test-key")
        assert isinstance(client, GeminiChatClient)
