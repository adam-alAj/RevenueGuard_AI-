"""Smoke test agent — proves the full request → tool-call → structured-response loop.

This agent uses the Gemini client with the smoke_test_greet tool to verify
the Microsoft Agent Framework integration end-to-end.
"""

from __future__ import annotations

import logging

from agent_framework import Agent

from app.agents.gemini_client import create_gemini_client
from app.agents.tools.smoke_test import smoke_test_greet

logger = logging.getLogger(__name__)

SMOKE_TEST_INSTRUCTIONS = (
    "You are a test agent. When the user asks you to greet someone, "
    "use the smoke_test_greet tool. Always use the tool, never answer "
    "from your own knowledge."
)


def create_smoke_test_agent(
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> Agent:
    """Create the smoke test agent.

    Args:
        api_key: GEMINI_API_KEY (must not be empty).
        model: Gemini model identifier.

    Returns:
        Configured Agent instance.

    Raises:
        GeminiClientError: If api_key is empty.
    """
    client = create_gemini_client(api_key=api_key, model=model)

    return Agent(
        client=client,
        instructions=SMOKE_TEST_INSTRUCTIONS,
        name="smoke-test-agent",
        description="Trivial agent for verifying the MAF+Gemini integration",
        tools=[smoke_test_greet],
    )
