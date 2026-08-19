"""Tests for recovery metrics — multi-case fixture, recovery rate computation.

Verifies:
- Multi-case fixture produces correct aggregate metrics
- Recovery rate computation (recovered / potential)
- Edge cases (zero potential, all recovered, none recovered)
- Critical case counting
- Open case counting
"""

from __future__ import annotations

from decimal import Decimal

from app.services.verification.metrics import (
    CaseMetricsInput,
    compute_org_metrics,
)


class TestMultiCaseFixture:
    """Multi-case fixture with various statuses and amounts."""

    def test_mixed_status_fixture(self) -> None:
        """Fixture with detected, recovered, closed, and open cases."""
        cases = [
            # Detected case
            CaseMetricsInput(
                case_id="c1",
                organization_id="org-001",
                status="detected",
                severity="high",
                potential_leakage=Decimal("10000.00"),
            ),
            # Recovered case
            CaseMetricsInput(
                case_id="c2",
                organization_id="org-001",
                status="recovered",
                severity="critical",
                potential_leakage=Decimal("20000.00"),
                recovered_amount=Decimal("20000.00"),
            ),
            # Partially recovered case
            CaseMetricsInput(
                case_id="c3",
                organization_id="org-001",
                status="action_completed",
                severity="medium",
                potential_leakage=Decimal("15000.00"),
                recovered_amount=Decimal("10000.00"),
            ),
            # Closed (false positive)
            CaseMetricsInput(
                case_id="c4",
                organization_id="org-001",
                status="false_positive",
                severity="low",
                potential_leakage=Decimal("5000.00"),
            ),
            # Recovered with partial amount
            CaseMetricsInput(
                case_id="c5",
                organization_id="org-001",
                status="recovered",
                severity="high",
                potential_leakage=Decimal("8000.00"),
                recovered_amount=Decimal("6000.00"),
            ),
        ]

        metrics = compute_org_metrics("org-001", cases)

        # Total potential: 10k + 20k + 15k + 5k + 8k = 58k
        assert metrics.total_potential_leakage == Decimal("58000.00")

        # Total recovered: 20k (c2) + 10k (c3 partial) + 6k (c5) = 36k
        assert metrics.total_recovered_revenue == Decimal("36000.00")

        # Recovery rate: 36k / 58k = 0.621
        assert metrics.recovery_rate == Decimal("0.621")

        # Open cases: detected + action_completed = 2
        assert metrics.open_cases == 2

        # Critical cases: c2 = 1
        assert metrics.critical_cases == 1

        # Total cases
        assert metrics.total_cases == 5

        # Recovered cases: c2 + c5 = 2
        assert metrics.recovered_cases == 2

    def test_confirmed_leakage_includes_later_statuses(self) -> None:
        """Confirmed leakage includes all statuses after investigation."""
        cases = [
            CaseMetricsInput(
                case_id="c1",
                organization_id="org-001",
                status="approved",
                potential_leakage=Decimal("10000.00"),
            ),
            CaseMetricsInput(
                case_id="c2",
                organization_id="org-001",
                status="action_pending",
                potential_leakage=Decimal("5000.00"),
            ),
            CaseMetricsInput(
                case_id="c3",
                organization_id="org-001",
                status="closed",
                potential_leakage=Decimal("3000.00"),
            ),
            CaseMetricsInput(
                case_id="c4",
                organization_id="org-001",
                status="detected",
                potential_leakage=Decimal("7000.00"),
            ),
        ]

        metrics = compute_org_metrics("org-001", cases)

        # Confirmed = approved + action_pending + closed = 10k + 5k + 3k = 18k
        assert metrics.total_confirmed_leakage == Decimal("18000.00")


class TestRecoveryRate:
    """Recovery rate computation edge cases."""

    def test_zero_potential(self) -> None:
        """Zero potential leakage → recovery rate is 0."""
        cases = [
            CaseMetricsInput(
                case_id="c1",
                organization_id="org-001",
                status="recovered",
                potential_leakage=Decimal("0.00"),
                recovered_amount=Decimal("0.00"),
            ),
        ]
        metrics = compute_org_metrics("org-001", cases)
        assert metrics.recovery_rate == Decimal("0.000")

    def test_100_percent_recovery(self) -> None:
        """All cases fully recovered → recovery rate is 1.000."""
        cases = [
            CaseMetricsInput(
                case_id="c1",
                organization_id="org-001",
                status="recovered",
                potential_leakage=Decimal("10000.00"),
                recovered_amount=Decimal("10000.00"),
            ),
            CaseMetricsInput(
                case_id="c2",
                organization_id="org-001",
                status="recovered",
                potential_leakage=Decimal("5000.00"),
                recovered_amount=Decimal("5000.00"),
            ),
        ]
        metrics = compute_org_metrics("org-001", cases)
        assert metrics.recovery_rate == Decimal("1.000")

    def test_zero_recovery(self) -> None:
        """No cases recovered → recovery rate is 0."""
        cases = [
            CaseMetricsInput(
                case_id="c1",
                organization_id="org-001",
                status="action_completed",
                potential_leakage=Decimal("10000.00"),
            ),
        ]
        metrics = compute_org_metrics("org-001", cases)
        assert metrics.recovery_rate == Decimal("0.000")

    def test_empty_cases(self) -> None:
        """No cases → all metrics are zero."""
        metrics = compute_org_metrics("org-001", [])
        assert metrics.total_potential_leakage == Decimal("0")
        assert metrics.total_recovered_revenue == Decimal("0")
        assert metrics.recovery_rate == Decimal("0.000")
        assert metrics.total_cases == 0
        assert metrics.open_cases == 0


class TestCriticalCases:
    """Critical case counting."""

    def test_critical_count(self) -> None:
        """Only critical-severity cases are counted."""
        cases = [
            CaseMetricsInput(
                case_id="c1",
                organization_id="org-001",
                status="detected",
                severity="critical",
                potential_leakage=Decimal("10000"),
            ),
            CaseMetricsInput(
                case_id="c2",
                organization_id="org-001",
                status="detected",
                severity="high",
                potential_leakage=Decimal("5000"),
            ),
            CaseMetricsInput(
                case_id="c3",
                organization_id="org-001",
                status="detected",
                severity="critical",
                potential_leakage=Decimal("8000"),
            ),
        ]
        metrics = compute_org_metrics("org-001", cases)
        assert metrics.critical_cases == 2


class TestOpenCases:
    """Open case counting."""

    def test_open_case_statuses(self) -> None:
        """All non-closed statuses count as open."""
        open_statuses = [
            "detected",
            "investigating",
            "pending_review",
            "approved",
            "action_pending",
            "action_completed",
            "verified",
        ]
        cases = [
            CaseMetricsInput(
                case_id=f"c{i}",
                organization_id="org-001",
                status=status,
                potential_leakage=Decimal("1000"),
            )
            for i, status in enumerate(open_statuses)
        ]
        metrics = compute_org_metrics("org-001", cases)
        assert metrics.open_cases == 7

    def test_closed_not_counted(self) -> None:
        """Closed/recovered/false_positive/legitimate_exception not counted as open."""
        closed_statuses = [
            "closed",
            "recovered",
            "false_positive",
            "legitimate_exception",
            "rejected",
        ]
        cases = [
            CaseMetricsInput(
                case_id=f"c{i}",
                organization_id="org-001",
                status=status,
                potential_leakage=Decimal("1000"),
            )
            for i, status in enumerate(closed_statuses)
        ]
        metrics = compute_org_metrics("org-001", cases)
        assert metrics.open_cases == 0


class TestSerialization:
    """Tests for to_dict serialization."""

    def test_to_dict(self) -> None:
        """OrgMetrics serializes correctly."""
        cases = [
            CaseMetricsInput(
                case_id="c1",
                organization_id="org-001",
                status="recovered",
                potential_leakage=Decimal("10000"),
                recovered_amount=Decimal("10000"),
            ),
        ]
        metrics = compute_org_metrics("org-001", cases)
        d = metrics.to_dict()

        assert d["organization_id"] == "org-001"
        assert d["total_potential_leakage"] == "10000"
        assert d["total_recovered_revenue"] == "10000"
        assert d["recovery_rate"] == "1.000"
        assert d["recovered_cases"] == 1
        assert d["open_cases"] == 0
