"""Smoke test tool — a trivial read-only tool for verifying the agent loop.

This tool returns a greeting message and proves the full
request → tool-call → structured-response loop works.
"""

from __future__ import annotations

from agent_framework import tool


@tool(name="smoke_test_greet", description="Returns a greeting message. Read-only, no side effects.")
def smoke_test_greet(name: str = "World") -> str:
    """Return a greeting for the given name.

    This is a trivial read-only tool used to verify the agent framework
    integration end-to-end. It performs no database operations, no
    mutations, and no external API calls.

    Args:
        name: The name to greet.

    Returns:
        A greeting string.
    """
    return f"Hello, {name}! RevenueGuard AI agent framework is working correctly."
