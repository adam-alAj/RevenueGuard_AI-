"""Org-level recovery metrics — computes the numbers that prove the product works.

Metrics computed:
- total_potential_leakage: Sum of potential_leakage across all cases
- total_confirmed_leakage: Sum for cases with status confirmed/likely
- total_recovered_revenue: Sum of recovered_amount for recovered cases
- open_cases: Cases not yet closed/recovered
- critical_cases: Cases with severity=critical
- recovery_rate: total_recovered / total_potential (0.0-1.0)

These metrics feed the Phase 14 dashboard and are the core success condition
of the product (spec §69).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass
class OrgMetrics:
    """Aggregated metrics for an organization."""

    organization_id: str
    total_potential_leakage: Decimal
    total_confirmed_leakage: Decimal
    total_recovered_revenue: Decimal
    open_cases: int
    critical_cases: int
    total_cases: int
    recovered_cases: int
    recovery_rate: Decimal  # 0.000 to 1.000

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "organization_id": self.organization_id,
            "total_potential_leakage": str(self.total_potential_leakage),
            "total_confirmed_leakage": str(self.total_confirmed_leakage),
            "total_recovered_revenue": str(self.total_recovered_revenue),
            "open_cases": self.open_cases,
            "critical_cases": self.critical_cases,
            "total_cases": self.total_cases,
            "recovered_cases": self.recovered_cases,
            "recovery_rate": str(self.recovery_rate),
        }


# Case statuses considered "open" (not resolved)
OPEN_STATUSES = {
    "detected", "investigating", "pending_review", "approved",
    "action_pending", "action_completed", "verified",
}

# Case statuses considered "recovered"
RECOVERED_STATUSES = {"recovered"}

# Case statuses considered "closed" (resolved, not recovered)
CLOSED_STATUSES = {"closed", "false_positive", "legitimate_exception", "rejected"}


@dataclass
class CaseMetricsInput:
    """Minimal case data needed for metrics computation."""

    case_id: str
    organization_id: str
    status: str
    severity: str | None = None
    potential_leakage: Decimal = Decimal("0")
    recovered_amount: Decimal = Decimal("0")


def compute_org_metrics(
    organization_id: str,
    cases: list[CaseMetricsInput],
) -> OrgMetrics:
    """Compute org-level recovery metrics from a list of cases.

    This is a pure function — no database access, no side effects.
    All inputs are provided explicitly.

    Args:
        organization_id: The organization to compute metrics for.
        cases: List of case data for this organization.

    Returns:
        OrgMetrics with all computed metrics.
    """
    total_potential = Decimal("0")
    total_confirmed = Decimal("0")
    total_recovered = Decimal("0")
    open_count = 0
    critical_count = 0
    total_count = len(cases)
    recovered_count = 0

    for case in cases:
        # Sum potential leakage
        total_potential += case.potential_leakage

        # Sum confirmed leakage (cases that went through investigation)
        if case.status in ("approved", "action_pending", "action_completed",
                           "verified", "recovered", "closed"):
            total_confirmed += case.potential_leakage

        # Sum recovered revenue
        if case.status in RECOVERED_STATUSES:
            total_recovered += case.recovered_amount
            recovered_count += 1
        elif case.recovered_amount > 0:
            # Partial recovery
            total_recovered += case.recovered_amount

        # Count open cases
        if case.status in OPEN_STATUSES:
            open_count += 1

        # Count critical cases
        if case.severity == "critical":
            critical_count += 1

    # Compute recovery rate
    if total_potential > 0:
        recovery_rate = (total_recovered / total_potential).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
    else:
        recovery_rate = Decimal("0.000")

    return OrgMetrics(
        organization_id=organization_id,
        total_potential_leakage=total_potential,
        total_confirmed_leakage=total_confirmed,
        total_recovered_revenue=total_recovered,
        open_cases=open_count,
        critical_cases=critical_count,
        total_cases=total_count,
        recovered_cases=recovered_count,
        recovery_rate=recovery_rate,
    )
