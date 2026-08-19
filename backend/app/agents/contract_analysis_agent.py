"""Contract Analysis Agent — extracts structured contract terms via Gemini.

This agent reads a contract and its line items, then produces a strict
ContractTerms model via Gemini's structured output mode. No free-text
decision fields — every field is typed.
"""

from __future__ import annotations

import json
import logging

from agent_framework import Agent

from app.agents.gemini_client import create_gemini_client
from app.agents.schemas import ContractTerms

logger = logging.getLogger(__name__)

CONTRACT_ANALYSIS_INSTRUCTIONS = """You are a contract analysis specialist for RevenueGuard AI.

Your task is to analyze a contract and extract key terms relevant to revenue leakage detection.

You have access to tools that can retrieve the contract, its line items, and related documents.

After gathering the necessary information, provide a structured analysis with:
- billing_frequency: How often the customer is billed
- unit_pricing_model: The pricing model used
- base_rate: The base rate or unit price
- currency: ISO 4217 currency code
- discount_cap_pct: Maximum discount percentage, if specified
- renewal_terms: How the contract renews
- minimum_commitment: Minimum spend commitment, if any
- expiration_date: When the contract expires
- has_evergreen_clause: Whether it auto-renews indefinitely
- termination_notice_days: Days notice required for termination
- summary: Brief summary of key terms

IMPORTANT: All fields must be filled in. Use "unknown" for renewal_terms if not specified.
For numeric fields, use null only if truly not present in the contract.
"""


def create_contract_analysis_agent(
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> Agent:
    """Create the Contract Analysis Agent.

    Args:
        api_key: GEMINI_API_KEY.
        model: Gemini model identifier.

    Returns:
        Configured Agent instance.
    """
    from app.agents.tools.investigation_tools import (
        get_contract_lines_tool,
        get_contract_tool,
    )

    client = create_gemini_client(api_key=api_key, model=model)

    return Agent(
        client=client,
        instructions=CONTRACT_ANALYSIS_INSTRUCTIONS,
        name="contract-analysis-agent",
        description="Analyzes contracts and extracts structured terms for leakage detection",
        tools=[get_contract_tool, get_contract_lines_tool],
    )


def parse_contract_terms(response_text: str) -> ContractTerms:
    """Parse the agent's response into a strict ContractTerms model.

    Attempts to extract JSON from the response and validate it
    against the ContractTerms schema.

    Args:
        response_text: The raw text response from the agent.

    Returns:
        Validated ContractTerms instance.

    Raises:
        ValueError: If the response cannot be parsed into valid ContractTerms.
    """
    # Try to extract JSON from the response
    text = response_text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` markers)
        json_lines = [line for line in lines[1:] if not line.strip().startswith("```")]
        text = "\n".join(json_lines)

    try:
        data = json.loads(text)
        return ContractTerms(**data)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find JSON object in the text
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            return ContractTerms(**data)
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"Could not parse ContractTerms from response: {response_text[:200]}...")
