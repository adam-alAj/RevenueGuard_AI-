"""Recovery Recommendation Agent — selects recovery action from closed vocabulary.

For confirmed/likely cases, this agent picks exactly one action from a
Pydantic Literal/enum field — the model cannot invent a new action type.
"""

from __future__ import annotations

import json
import logging

from agent_framework import Agent

from app.agents.gemini_client import create_gemini_client
from app.agents.schemas import RecoveryRecommendation

logger = logging.getLogger(__name__)

RECOVERY_RECOMMENDATION_INSTRUCTIONS = """You are a recovery specialist for RevenueGuard AI.

Your task is to recommend a specific recovery action for a confirmed or likely
revenue leakage case.

You have access to tools to retrieve relevant data about the customer, contract,
and financial records.

AVAILABLE ACTIONS (you MUST choose exactly one):
- create_invoice_draft: Create a new invoice for the missed amount
- send_payment_reminder: Send a reminder for overdue payment
- request_internal_investigation: Request deeper internal investigation
- correct_pricing: Correct a pricing error in the system
- contact_account_manager: Contact the account manager for resolution
- renew_contract: Initiate contract renewal to prevent future leakage
- reconcile_payment: Reconcile a payment discrepancy
- issue_correction: Issue a credit or debit correction
- escalate_to_finance_manager: Escalate to finance manager for review

URGENCY LEVELS:
- immediate: Action needed within 24 hours
- within_week: Action needed within 7 days
- within_month: Action needed within 30 days
- next_billing_cycle: Can wait until next billing cycle

IMPORTANT:
- Choose the MOST APPROPRIATE action based on the case details
- Provide a clear rationale citing specific evidence
- Set requires_approval=True for any action involving money movement
- If the case involves complex financial judgment, escalate to finance manager
"""


def create_recovery_recommendation_agent(
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> Agent:
    """Create the Recovery Recommendation Agent.

    Args:
        api_key: GEMINI_API_KEY.
        model: Gemini model identifier.

    Returns:
        Configured Agent instance.
    """
    from app.agents.tools.investigation_tools import (
        get_contract_tool,
        get_customer_tool,
        get_invoice_tool,
        get_payments_tool,
    )

    client = create_gemini_client(api_key=api_key, model=model)

    return Agent(
        client=client,
        instructions=RECOVERY_RECOMMENDATION_INSTRUCTIONS,
        name="recovery-recommendation-agent",
        description="Recommends specific recovery actions for confirmed leakage cases",
        tools=[
            get_customer_tool,
            get_contract_tool,
            get_invoice_tool,
            get_payments_tool,
        ],
    )


def parse_recovery_recommendation(response_text: str) -> RecoveryRecommendation:
    """Parse the agent's response into a strict RecoveryRecommendation model.

    Args:
        response_text: The raw text response from the agent.

    Returns:
        Validated RecoveryRecommendation instance.

    Raises:
        ValueError: If the response cannot be parsed into valid RecoveryRecommendation.
    """
    text = response_text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = [line for line in lines[1:] if not line.strip().startswith("```")]
        text = "\n".join(json_lines)

    try:
        data = json.loads(text)
        return RecoveryRecommendation(**data)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find JSON object in the text
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            return RecoveryRecommendation(**data)
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(
        f"Could not parse RecoveryRecommendation from response: {response_text[:200]}..."
    )
