"""Investigation Agent — gathers evidence, classifies leakage cases.

This agent takes a detected leakage candidate, gathers evidence (immutable
snapshots), explicitly searches for legitimate exceptions (amendments, credit
notes, disputes, cancellations), and returns a strict InvestigationResult
with a classification enum and evidence citations.
"""

from __future__ import annotations

import json
import logging

from agent_framework import Agent

from app.agents.gemini_client import create_gemini_client
from app.agents.schemas import InvestigationResult

logger = logging.getLogger(__name__)

INVESTIGATION_INSTRUCTIONS = """You are an investigative analyst for RevenueGuard AI.

Your task is to investigate a detected revenue leakage candidate and determine
whether it is a real leakage issue or a false positive/legitimate exception.

You have access to tools that can retrieve customers, contracts, invoices,
payments, projects, credit notes, and contract amendments.

INVESTIGATION PROCESS:
1. Retrieve the primary entities (contract, invoice, customer, project)
2. Gather supporting evidence (line items, payment history)
3. SEARCH FOR LEGITIMATE EXCEPTIONS:
   - Check for contract amendments that may have changed pricing/terms
   - Check for credit notes that may explain payment discrepancies
   - Check for project status changes or cancellations
   - Check for payment disputes or holds
4. Classify the case based on evidence

CLASSIFICATION RULES:
- confirmed: Clear evidence of leakage with no legitimate explanation
- likely: Strong evidence of leakage but some ambiguity remains
- uncertain: Insufficient evidence to make a determination
- false_positive: Evidence shows this is NOT actually leakage
- legitimate_exception: A valid business reason explains the discrepancy

IMPORTANT:
- Every explanation MUST cite specific evidence IDs
- If you cannot find enough evidence, classify as "uncertain" — do NOT guess
- If you find a legitimate explanation (amendment, credit note, etc.),
  classify as "legitimate_exception" with the specific reason
- Never fabricate evidence IDs — only cite IDs that were returned by tools
"""


def create_investigation_agent(
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> Agent:
    """Create the Investigation Agent.

    Args:
        api_key: GEMINI_API_KEY.
        model: Gemini model identifier.

    Returns:
        Configured Agent instance.
    """
    from app.agents.tools.investigation_tools import (
        get_contract_tool,
        get_customer_tool,
        get_invoice_lines_tool,
        get_invoice_tool,
        get_payments_tool,
        get_project_tool,
        search_contract_amendments_tool,
        search_credit_notes_tool,
        search_customer_history_tool,
    )

    client = create_gemini_client(api_key=api_key, model=model)

    return Agent(
        client=client,
        instructions=INVESTIGATION_INSTRUCTIONS,
        name="investigation-agent",
        description="Investigates leakage candidates, gathers evidence, classifies cases",
        tools=[
            get_customer_tool,
            get_contract_tool,
            get_invoice_tool,
            get_invoice_lines_tool,
            get_payments_tool,
            get_project_tool,
            search_customer_history_tool,
            search_credit_notes_tool,
            search_contract_amendments_tool,
        ],
    )


def parse_investigation_result(response_text: str) -> InvestigationResult:
    """Parse the agent's response into a strict InvestigationResult model.

    Args:
        response_text: The raw text response from the agent.

    Returns:
        Validated InvestigationResult instance.

    Raises:
        ValueError: If the response cannot be parsed into valid InvestigationResult.
    """
    text = response_text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = [line for line in lines[1:] if not line.strip().startswith("```")]
        text = "\n".join(json_lines)

    try:
        data = json.loads(text)
        return InvestigationResult(**data)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find JSON object in the text
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            return InvestigationResult(**data)
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(
        f"Could not parse InvestigationResult from response: {response_text[:200]}..."
    )
