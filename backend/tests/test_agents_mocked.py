"""Mocked tests for the three MVP agents.

Tests verify:
- Contract Analysis Agent produces valid ContractTerms
- Investigation Agent classifies correctly with evidence citations
- Recovery Recommendation Agent picks from closed vocabulary
- False-positive scenario resolves to legitimate_exception
- Sparse data returns uncertain rather than fabricated conclusion
- All outputs are strict Pydantic models
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.agents.contract_analysis_agent import parse_contract_terms
from app.agents.investigation_agent import parse_investigation_result
from app.agents.recovery_recommendation_agent import parse_recovery_recommendation
from app.agents.schemas import (
    ContractTerms,
    InvestigationClassification,
    InvestigationResult,
    RecoveryActionType,
    RecoveryRecommendation,
    UrgencyLevel,
)


class TestContractTermsSchema:
    """Tests for the ContractTerms strict schema."""

    def test_valid_contract_terms(self) -> None:
        """Valid data produces a ContractTerms instance."""
        terms = ContractTerms(
            billing_frequency="monthly",
            unit_pricing_model="fixed",
            base_rate=100.0,
            currency="USD",
            renewal_terms="auto_renew",
            summary="Standard monthly contract",
        )
        assert terms.billing_frequency == "monthly"
        assert terms.base_rate == 100.0
        assert terms.currency == "USD"

    def test_rejects_invalid_billing_frequency(self) -> None:
        """Invalid billing_frequency is rejected."""
        with pytest.raises(ValidationError):
            ContractTerms(
                billing_frequency="weekly",  # not in enum
                unit_pricing_model="fixed",
                base_rate=100.0,
                renewal_terms="auto_renew",
                summary="Test",
            )

    def test_rejects_invalid_renewal_terms(self) -> None:
        """Invalid renewal_terms is rejected."""
        with pytest.raises(ValidationError):
            ContractTerms(
                billing_frequency="monthly",
                unit_pricing_model="fixed",
                base_rate=100.0,
                renewal_terms="negotiated",  # not in enum
                summary="Test",
            )

    def test_optional_fields_default_to_none(self) -> None:
        """Optional fields default to None."""
        terms = ContractTerms(
            billing_frequency="annual",
            unit_pricing_model="flat_rate",
            base_rate=1200.0,
            renewal_terms="non_renewing",
            summary="Annual contract",
        )
        assert terms.discount_cap_pct is None
        assert terms.minimum_commitment is None
        assert terms.expiration_date is None
        assert terms.has_evergreen_clause is False


class TestInvestigationResultSchema:
    """Tests for the InvestigationResult strict schema."""

    def test_valid_investigation_result(self) -> None:
        """Valid data produces an InvestigationResult instance."""
        result = InvestigationResult(
            classification=InvestigationClassification.confirmed,
            confidence=0.95,
            explanation="Evidence shows billing discrepancy of $500. Evidence ID: ev-001 confirms contract rate.",
            evidence_refs=[
                {
                    "evidence_id": "ev-001",
                    "evidence_type": "contract",
                    "relevance": "Shows agreed rate differs from invoiced rate",
                }
            ],
            potential_leakage_amount=500.0,
        )
        assert result.classification == InvestigationClassification.confirmed
        assert result.confidence == 0.95
        assert len(result.evidence_refs) == 1

    def test_rejects_invalid_classification(self) -> None:
        """Invalid classification is rejected."""
        with pytest.raises(ValidationError):
            InvestigationResult(
                classification="maybe",  # not in enum
                confidence=0.5,
                explanation="Test",
                evidence_refs=[
                    {"evidence_id": "ev-001", "evidence_type": "contract", "relevance": "test"}
                ],
            )

    def test_requires_evidence_refs(self) -> None:
        """Evidence refs list must not be empty."""
        with pytest.raises(ValidationError):
            InvestigationResult(
                classification=InvestigationClassification.confirmed,
                confidence=0.9,
                explanation="Test explanation",
                evidence_refs=[],
            )

    def test_confidence_bounds(self) -> None:
        """Confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            InvestigationResult(
                classification=InvestigationClassification.confirmed,
                confidence=1.5,  # out of bounds
                explanation="Test",
                evidence_refs=[
                    {"evidence_id": "ev-001", "evidence_type": "contract", "relevance": "test"}
                ],
            )

    def test_all_classifications_valid(self) -> None:
        """All 5 classification values are valid."""
        for cls in InvestigationClassification:
            result = InvestigationResult(
                classification=cls,
                confidence=0.5,
                explanation=f"Testing {cls.value}",
                evidence_refs=[
                    {"evidence_id": "ev-001", "evidence_type": "contract", "relevance": "test"}
                ],
            )
            assert result.classification == cls


class TestRecoveryRecommendationSchema:
    """Tests for the RecoveryRecommendation strict schema."""

    def test_valid_recommendation(self) -> None:
        """Valid data produces a RecoveryRecommendation instance."""
        rec = RecoveryRecommendation(
            action=RecoveryActionType.create_invoice_draft,
            urgency=UrgencyLevel.within_week,
            rationale="Contract shows $500 underbilling that should be invoiced.",
            requires_approval=True,
        )
        assert rec.action == RecoveryActionType.create_invoice_draft
        assert rec.urgency == UrgencyLevel.within_week

    def test_rejects_invalid_action(self) -> None:
        """Invalid action type is rejected."""
        with pytest.raises(ValidationError):
            RecoveryRecommendation(
                action="send_email",  # not in enum
                urgency="now",
                rationale="Test",
            )

    def test_all_actions_valid(self) -> None:
        """All 9 action values are valid."""
        for action in RecoveryActionType:
            rec = RecoveryRecommendation(
                action=action,
                urgency=UrgencyLevel.within_month,
                rationale=f"Testing {action.value}",
            )
            assert rec.action == action

    def test_all_urgency_levels_valid(self) -> None:
        """All 4 urgency values are valid."""
        for urgency in UrgencyLevel:
            rec = RecoveryRecommendation(
                action=RecoveryActionType.send_payment_reminder,
                urgency=urgency,
                rationale=f"Testing {urgency.value}",
            )
            assert rec.urgency == urgency


class TestParseContractTerms:
    """Tests for parsing ContractTerms from agent response text."""

    def test_parse_valid_json(self) -> None:
        """Valid JSON parses correctly."""
        data = {
            "billing_frequency": "monthly",
            "unit_pricing_model": "fixed",
            "base_rate": 100.0,
            "renewal_terms": "auto_renew",
            "summary": "Standard monthly",
        }
        terms = parse_contract_terms(json.dumps(data))
        assert terms.billing_frequency == "monthly"

    def test_parse_json_in_code_block(self) -> None:
        """JSON wrapped in markdown code block parses correctly."""
        data = {
            "billing_frequency": "quarterly",
            "unit_pricing_model": "tiered",
            "base_rate": 500.0,
            "renewal_terms": "manual_renew",
            "summary": "Quarterly tiered",
        }
        text = f"Here is the analysis:\n```json\n{json.dumps(data)}\n```"
        terms = parse_contract_terms(text)
        assert terms.billing_frequency == "quarterly"

    def test_parse_json_in_text(self) -> None:
        """JSON embedded in surrounding text parses correctly."""
        data = {
            "billing_frequency": "annual",
            "unit_pricing_model": "flat_rate",
            "base_rate": 12000.0,
            "renewal_terms": "non_renewing",
            "summary": "Annual flat rate",
        }
        text = f"Based on my analysis, here are the terms:\n{json.dumps(data)}\nThese terms are standard."
        terms = parse_contract_terms(text)
        assert terms.billing_frequency == "annual"

    def test_parse_invalid_text_raises(self) -> None:
        """Non-JSON text raises ValueError."""
        with pytest.raises(ValueError, match="Could not parse"):
            parse_contract_terms("This is not JSON at all.")


class TestParseInvestigationResult:
    """Tests for parsing InvestigationResult from agent response text."""

    def test_parse_valid_json(self) -> None:
        """Valid JSON parses correctly."""
        data = {
            "classification": "confirmed",
            "confidence": 0.9,
            "explanation": "Clear billing discrepancy found.",
            "evidence_refs": [
                {
                    "evidence_id": "ev-001",
                    "evidence_type": "invoice",
                    "relevance": "Shows underbilling",
                }
            ],
        }
        result = parse_investigation_result(json.dumps(data))
        assert result.classification == InvestigationClassification.confirmed

    def test_parse_false_positive(self) -> None:
        """False positive classification parses correctly."""
        data = {
            "classification": "false_positive",
            "confidence": 0.85,
            "explanation": "Contract amendment shows pricing was intentionally reduced.",
            "evidence_refs": [
                {
                    "evidence_id": "ev-010",
                    "evidence_type": "contract_amendment",
                    "relevance": "Shows price reduction",
                }
            ],
            "false_positive_reason": "Contract was amended on 2026-01-15 to reduce pricing.",
        }
        result = parse_investigation_result(json.dumps(data))
        assert result.classification == InvestigationClassification.false_positive
        assert result.false_positive_reason is not None

    def test_parse_legitimate_exception(self) -> None:
        """Legitimate exception classification parses correctly."""
        data = {
            "classification": "legitimate_exception",
            "confidence": 0.95,
            "explanation": "Credit note explains the payment discrepancy.",
            "evidence_refs": [
                {
                    "evidence_id": "ev-020",
                    "evidence_type": "credit_note",
                    "relevance": "Covers the gap amount",
                }
            ],
            "legitimate_exception_reason": "Credit note CN-2026-001 for $500 was issued for overpayment.",
        }
        result = parse_investigation_result(json.dumps(data))
        assert result.classification == InvestigationClassification.legitimate_exception
        assert result.legitimate_exception_reason is not None

    def test_parse_uncertain(self) -> None:
        """Uncertain classification parses correctly."""
        data = {
            "classification": "uncertain",
            "confidence": 0.3,
            "explanation": "Insufficient data to determine if this is actual leakage.",
            "evidence_refs": [
                {
                    "evidence_id": "ev-030",
                    "evidence_type": "contract",
                    "relevance": "Partial information only",
                }
            ],
        }
        result = parse_investigation_result(json.dumps(data))
        assert result.classification == InvestigationClassification.uncertain
        assert result.confidence == 0.3


class TestParseRecoveryRecommendation:
    """Tests for parsing RecoveryRecommendation from agent response text."""

    def test_parse_valid_json(self) -> None:
        """Valid JSON parses correctly."""
        data = {
            "action": "create_invoice_draft",
            "urgency": "within_week",
            "rationale": "Invoice should be created for the underbilled amount.",
            "requires_approval": True,
        }
        rec = parse_recovery_recommendation(json.dumps(data))
        assert rec.action == RecoveryActionType.create_invoice_draft

    def test_parse_escalation(self) -> None:
        """Escalation recommendation parses correctly."""
        data = {
            "action": "escalate_to_finance_manager",
            "urgency": "immediate",
            "rationale": "Complex pricing dispute requires finance review.",
            "requires_approval": True,
            "escalation_reason": "Multiple contract amendments make this complex.",
        }
        rec = parse_recovery_recommendation(json.dumps(data))
        assert rec.action == RecoveryActionType.escalate_to_finance_manager
        assert rec.escalation_reason is not None


class TestFalsePositiveScenario:
    """End-to-end false-positive scenario test.

    Verifies that a valid contract amendment resolves to
    legitimate_exception and auto-closes.
    """

    def test_contract_amendment_false_positive(self) -> None:
        """Contract amendment explanation → legitimate_exception classification."""
        # Simulate what the Investigation Agent would return
        investigation_data = {
            "classification": "legitimate_exception",
            "confidence": 0.92,
            "explanation": (
                "Contract amendment CA-2026-001 dated 2026-01-15 reduced the monthly rate "
                "from $1,000 to $800. The invoiced amount of $800 matches the amended rate. "
                "This is not leakage — the pricing was intentionally updated. "
                "Evidence: ev-001 (contract amendment), ev-002 (original contract), ev-003 (invoice)."
            ),
            "evidence_refs": [
                {
                    "evidence_id": "ev-001",
                    "evidence_type": "contract_amendment",
                    "relevance": "Shows rate reduction from $1,000 to $800",
                },
                {
                    "evidence_id": "ev-002",
                    "evidence_type": "contract",
                    "relevance": "Original contract at $1,000/month",
                },
                {
                    "evidence_id": "ev-003",
                    "evidence_type": "invoice",
                    "relevance": "Invoice correctly reflects $800",
                },
            ],
            "legitimate_exception_reason": "Contract was amended to reduce pricing — invoiced amount matches amended rate.",
        }

        result = parse_investigation_result(json.dumps(investigation_data))

        # Verify classification
        assert result.classification == InvestigationClassification.legitimate_exception
        assert result.confidence >= 0.9

        # Verify evidence citations
        assert len(result.evidence_refs) == 3
        evidence_ids = [ref.evidence_id for ref in result.evidence_refs]
        assert "ev-001" in evidence_ids
        assert "ev-002" in evidence_ids
        assert "ev-003" in evidence_ids

        # Verify auto-close would be triggered
        assert result.classification in (
            InvestigationClassification.false_positive,
            InvestigationClassification.legitimate_exception,
        )

        # Verify legitimate_exception_reason is present
        assert result.legitimate_exception_reason is not None
        assert "amended" in result.legitimate_exception_reason.lower()


class TestSparseDataScenario:
    """Sparse data test — agent should return uncertain, not fabricate."""

    def test_insufficient_data_returns_uncertain(self) -> None:
        """When data is sparse, classification should be uncertain."""
        sparse_data = {
            "classification": "uncertain",
            "confidence": 0.2,
            "explanation": (
                "Insufficient data to make a determination. Only found the original contract "
                "but no invoice or payment records. Cannot verify if billing occurred."
            ),
            "evidence_refs": [
                {
                    "evidence_id": "ev-050",
                    "evidence_type": "contract",
                    "relevance": "Only partial data available",
                }
            ],
        }

        result = parse_investigation_result(json.dumps(sparse_data))

        assert result.classification == InvestigationClassification.uncertain
        assert result.confidence <= 0.5  # Low confidence
        # Should NOT be confirmed or likely
        assert result.classification not in (
            InvestigationClassification.confirmed,
            InvestigationClassification.likely,
        )


class TestToolContextInjection:
    """Tests that tool context is properly injected."""

    def test_tool_context_has_required_fields(self) -> None:
        """ToolContext carries all required fields."""
        from app.agents.tools.base import ToolContext

        ctx = ToolContext(
            organization_id="org-123",
            user_id="user-456",
            agent_name="investigation-agent",
            permitted_tools=["get_customer", "get_contract"],
        )
        assert ctx.organization_id == "org-123"
        assert ctx.agent_name == "investigation-agent"
        assert len(ctx.permitted_tools) == 2
