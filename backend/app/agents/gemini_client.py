"""Gemini client wrapper for Microsoft Agent Framework.

Provides a typed error when GEMINI_API_KEY is missing, and a factory
function to create properly-configured GeminiChatClient instances.
"""

from __future__ import annotations

from agent_framework_gemini import GeminiChatClient, GeminiChatOptions


class GeminiClientError(Exception):
    """Raised when the Gemini client cannot be initialized."""


def create_gemini_client(
    api_key: str,
    model: str = "gemini-2.0-flash",
    temperature: float = 0.7,
) -> GeminiChatClient:
    """Create a configured GeminiChatClient.

    Args:
        api_key: The GEMINI_API_KEY. Must not be empty.
        model: The Gemini model identifier.
        temperature: Default sampling temperature.

    Returns:
        Configured GeminiChatClient instance.

    Raises:
        GeminiClientError: If api_key is empty or missing.
    """
    if not api_key:
        raise GeminiClientError(
            "GEMINI_API_KEY is required but was not provided. "
            "Set it via environment variable — refusing to start without it."
        )

    return GeminiChatClient(
        api_key=api_key,
        model=model,
    )


def create_default_options(temperature: float = 0.7) -> GeminiChatOptions:
    """Create default GeminiChatOptions.

    Args:
        temperature: Sampling temperature (0.0-2.0).

    Returns:
        GeminiChatOptions dict.
    """
    return GeminiChatOptions(temperature=temperature)
