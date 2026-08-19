"""Explanation builder — combines agent narrative with deterministic calculations.

Builds the final case explanation text by combining:
1. The Investigation Agent's evidence-cited narrative
2. The deterministic financial calculation
3. The confidence breakdown
4. The severity/priority classification

This produces a complete, auditable explanation that can be presented to
a finance manager for review.
"""

from __future__ import annotations

from app.scoring.confidence import ConfidenceBreakdown
from app.scoring.financial_impact import FinancialImpact, FinancialImpactCalculator
from app.scoring.severity_priority import PriorityResult, SeverityResult


def build_case_explanation(
    agent_explanation: str,
    financial_impact: FinancialImpact,
    confidence_breakdown: ConfidenceBreakdown,
    severity_result: SeverityResult,
    priority_result: PriorityResult,
    evidence_count: int = 0,
    leakage_type: str = "",
) -> str:
    """Build a complete, auditable case explanation.

    Combines the agent's narrative with deterministic calculations
    into a single explanation text.

    Args:
        agent_explanation: The Investigation Agent's evidence-cited explanation.
        financial_impact: Deterministic financial impact calculation.
        confidence_breakdown: Versioned confidence score breakdown.
        severity_result: Severity classification result.
        priority_result: Priority classification result.
        evidence_count: Number of evidence records attached.
        leakage_type: The type of leakage detected.

    Returns:
        Complete explanation text.
    """
    sections = []

    # Section 1: Summary
    sections.append("=== LEAKAGE CASE ANALYSIS ===")
    if leakage_type:
        sections.append(f"Type: {leakage_type.replace('_', ' ').title()}")
    sections.append("")

    # Section 2: Financial Impact (deterministic)
    sections.append("--- Financial Impact (Deterministic) ---")
    sections.append(
        f"Expected amount:  {FinancialImpactCalculator.format_currency(financial_impact.expected_amount)}"
    )
    sections.append(
        f"Actual amount:    {FinancialImpactCalculator.format_currency(financial_impact.actual_amount)}"
    )
    sections.append(
        f"Potential leakage: {FinancialImpactCalculator.format_currency(financial_impact.potential_leakage)}"
    )
    sections.append(
        f"Recoverable:      {FinancialImpactCalculator.format_currency(financial_impact.recoverable_amount)}"
    )
    sections.append("")

    # Section 3: Confidence Score (versioned, decomposed)
    sections.append(f"--- Confidence Score ({confidence_breakdown.formula_version}) ---")
    sections.append(f"Final confidence: {confidence_breakdown.final_confidence:.1%}")
    sections.append("Components:")
    sections.append(
        f"  Detection strength:       {confidence_breakdown.detection_strength:.1%} "
        f"(weight: {confidence_breakdown.weights['detection_strength']:.0%})"
    )
    sections.append(
        f"  Entity resolution:        {confidence_breakdown.entity_resolution_confidence:.1%} "
        f"(weight: {confidence_breakdown.weights['entity_resolution']:.0%})"
    )
    sections.append(
        f"  Evidence completeness:    {confidence_breakdown.evidence_completeness:.1%} "
        f"(weight: {confidence_breakdown.weights['evidence_completeness']:.0%})"
    )
    sections.append(
        f"  Agent classification:     {confidence_breakdown.classification} "
        f"-> {confidence_breakdown.classification_contribution:.1%} "
        f"(weight: {confidence_breakdown.weights['classification']:.0%})"
    )
    sections.append("")

    # Section 4: Classification
    sections.append("--- Classification ---")
    sections.append(f"Severity: {severity_result.severity.upper()}")
    sections.append(f"  Reason: {severity_result.reason}")
    sections.append(f"Priority: {priority_result.priority}")
    sections.append(f"  Reason: {priority_result.reason}")
    sections.append(f"Case age: {severity_result.age_days} days")
    sections.append("")

    # Section 5: Agent Investigation Narrative
    sections.append("--- Agent Investigation ---")
    sections.append(f"Evidence records: {evidence_count}")
    sections.append(agent_explanation)
    sections.append("")

    sections.append("=== END ANALYSIS ===")

    return "\n".join(sections)


def build_confidence_summary(breakdown: ConfidenceBreakdown) -> str:
    """Build a one-line confidence summary for dashboards.

    Example: "93.7% (detection: 95%, entity: 98%, evidence: 90%, classification: confirmed)"
    """
    return (
        f"{breakdown.final_confidence:.1%} "
        f"(detection: {breakdown.detection_strength:.0%}, "
        f"entity: {breakdown.entity_resolution_confidence:.0%}, "
        f"evidence: {breakdown.evidence_completeness:.0%}, "
        f"classification: {breakdown.classification})"
    )


def build_financial_summary(impact: FinancialImpact) -> str:
    """Build a one-line financial summary for dashboards.

    Example: "Expected $15,000.00, Actual $12,000.00, Leakage $3,000.00"
    """
    return (
        f"Expected {FinancialImpactCalculator.format_currency(impact.expected_amount)}, "
        f"Actual {FinancialImpactCalculator.format_currency(impact.actual_amount)}, "
        f"Leakage {FinancialImpactCalculator.format_currency(impact.potential_leakage)}"
    )
