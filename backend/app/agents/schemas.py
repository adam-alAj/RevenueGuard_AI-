"""Strict Pydantic schemas for agent structured outputs.

Every decision field uses enums or Literal types — no free-text fields
where a decision is required. This enforces:
- Investigation classifications are one of exactly 5 values
- Recovery actions are one of exactly 9 values
- All explanations cite specific evidence_ids
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# --- Enums ---


class InvestigationClassification(str, Enum):
    """Classification of a leakage case after investigation."""

    confirmed = "confirmed"
    likely = "likely"
    uncertain = "uncertain"
    false_positive = "false_positive"
    legitimate_exception = "legitimate_exception"


class RecoveryActionType(str, Enum):
    """Closed vocabulary of recovery actions. The model cannot invent new types."""

    create_invoice_draft = "create_invoice_draft"
    send_payment_reminder = "send_payment_reminder"
    request_internal_investigation = "request_internal_investigation"
    correct_pricing = "correct_pricing"
    contact_account_manager = "contact_account_manager"
    renew_contract = "renew_contract"
    reconcile_payment = "reconcile_payment"
    issue_correction = "issue_correction"
    escalate_to_finance_manager = "escalate_to_finance_manager"


class UrgencyLevel(str, Enum):
    """Urgency of the recommended recovery action."""

    immediate = "immediate"
    within_week = "within_week"
    within_month = "within_month"
    next_billing_cycle = "next_billing_cycle"


# --- Contract Analysis Output ---


class ContractTerms(BaseModel):
    """Structured extraction of key contract terms for leakage analysis.

    Produced by the Contract Analysis Agent via Gemini structured output.
    All fields are strict — no optional free-text where a decision matters.
    """

    billing_frequency: Literal["monthly", "quarterly", "semi_annual", "annual", "one_time", "usage_based"] = (
        Field(description="How often the customer is billed")
    )
    unit_pricing_model: Literal["fixed", "tiered", "volume", "usage_based", "flat_rate"] = (
        Field(description="Pricing model used in the contract")
    )
    base_rate: float = Field(description="Base rate or unit price in the contract currency")
    currency: str = Field(description="ISO 4217 currency code", default="USD")
    discount_cap_pct: float | None = Field(
        description="Maximum discount percentage allowed, if specified",
        default=None,
        ge=0,
        le=100,
    )
    renewal_terms: Literal["auto_renew", "manual_renew", "non_renewing", "unknown"] = (
        Field(description="How the contract renews")
    )
    minimum_commitment: float | None = Field(
        description="Minimum spend or quantity commitment, if any",
        default=None,
        ge=0,
    )
    expiration_date: date | None = Field(
        description="Contract expiration date",
        default=None,
    )
    has_evergreen_clause: bool = Field(
        description="Whether the contract has an evergreen (auto-renewal) clause",
        default=False,
    )
    termination_notice_days: int | None = Field(
        description="Days notice required for termination",
        default=None,
        ge=0,
    )
    summary: str = Field(
        description="Brief summary of key terms relevant to leakage detection",
        max_length=500,
    )


# --- Investigation Output ---


class EvidenceReference(BaseModel):
    """A reference to a specific evidence record cited in the investigation."""

    evidence_id: str = Field(description="UUID of the Evidence record")
    evidence_type: str = Field(description="Type of evidence (contract, invoice, payment, etc.)")
    relevance: str = Field(description="How this evidence supports the classification")


class InvestigationResult(BaseModel):
    """Structured output from the Investigation Agent.

    The classification enum restricts to exactly 5 values.
    Every explanation must cite specific evidence_ids — not free text alone.
    """

    classification: InvestigationClassification = Field(
        description="Final classification of the leakage case"
    )
    confidence: float = Field(
        description="Confidence in the classification (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    explanation: str = Field(
        description="Detailed explanation of the classification with evidence citations",
        max_length=2000,
    )
    evidence_refs: list[EvidenceReference] = Field(
        description="Specific evidence records supporting this classification",
        min_length=1,
    )
    potential_leakage_amount: float | None = Field(
        description="Confirmed potential leakage amount in the contract currency",
        default=None,
        ge=0,
    )
    legitimate_exception_reason: str | None = Field(
        description="If legitimate_exception, the specific reason",
        default=None,
    )
    false_positive_reason: str | None = Field(
        description="If false_positive, the specific reason",
        default=None,
    )
    next_steps: list[str] = Field(
        description="Recommended next steps",
        default_factory=list,
    )


# --- Recovery Recommendation Output ---


class RecoveryRecommendation(BaseModel):
    """Structured output from the Recovery Recommendation Agent.

    The action field uses a Literal type restricting to exactly 9 values.
    The model cannot invent new action types.
    """

    action: RecoveryActionType = Field(
        description="Recommended recovery action"
    )
    urgency: UrgencyLevel = Field(
        description="How urgently this action should be taken"
    )
    rationale: str = Field(
        description="Why this specific action is recommended, citing evidence",
        max_length=1000,
    )
    estimated_recovery_amount: float | None = Field(
        description="Estimated amount recoverable through this action",
        default=None,
        ge=0,
    )
    requires_approval: bool = Field(
        description="Whether this action requires human approval before execution",
        default=True,
    )
    escalation_reason: str | None = Field(
        description="If escalating, why this needs finance manager attention",
        default=None,
    )
    supporting_evidence_ids: list[str] = Field(
        description="Evidence IDs supporting this recommendation",
        default_factory=list,
    )


# --- Workflow State ---


class WorkflowState(BaseModel):
    """State passed through the investigation workflow steps."""

    case_id: str
    organization_id: str
    leakage_type: str
    status: str = "detected"
    contract_terms: ContractTerms | None = None
    investigation_result: InvestigationResult | None = None
    recovery_recommendation: RecoveryRecommendation | None = None
    auto_closed: bool = False
    close_reason: str | None = None
    error: str | None = None
    steps_completed: list[str] = Field(default_factory=list)
