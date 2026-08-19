"""Tests for the verification executor — worked example, partial verification, grace period.

Verifies:
- Worked example: $20,000 leakage → invoice created → payment received → recovered
- Partial verification: invoice exists but unpaid → verified, not recovered
- Grace period: no invoice after N days → needs_follow_up
- Amount tolerance matching
- Cross-tenant isolation
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.verification.verification_executor import (
    CaseRecord,
    InvoiceRecord,
    PaymentRecord,
    VerificationExecutor,
    clear_verification_data,
    set_verification_data,
)


@pytest.fixture(autouse=True)
def _clear_state() -> None:
    """Clear verification data before each test."""
    clear_verification_data()
    yield
    clear_verification_data()


class TestWorkedExample:
    """Worked example: $20,000 leakage → invoice → payment → recovered."""

    def test_full_recovery_cycle(self) -> None:
        """$20,000 leakage → invoice for $20,000 → payment of $20,000 → recovered."""
        now = time()
        today = date(2026, 8, 19)

        set_verification_data(
            cases={
                "case-001": CaseRecord(
                    case_id="case-001",
                    organization_id="org-001",
                    status="action_completed",
                    customer_id="cust-001",
                    contract_id="cont-001",
                    potential_leakage=Decimal("20000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=now - 86400,  # 1 day ago
                ),
            },
            invoices={
                "inv-001": InvoiceRecord(
                    invoice_id="inv-001",
                    organization_id="org-001",
                    customer_id="cust-001",
                    contract_id="cont-001",
                    total=Decimal("20000.00"),
                    outstanding_balance=Decimal("0.00"),
                    status="paid",
                    issued_date=today - timedelta(days=5),
                    created_at=now - 7200,  # 2 hours after action
                ),
            },
            payments={
                "pay-001": PaymentRecord(
                    payment_id="pay-001",
                    organization_id="org-001",
                    customer_id="cust-001",
                    invoice_id="inv-001",
                    amount=Decimal("20000.00"),
                    payment_date=today - timedelta(days=3),
                    created_at=now - 3600,
                ),
            },
        )

        executor = VerificationExecutor()
        result = executor.check("case-001", today=today)

        assert result.verified is True
        assert result.status == "recovered"
        assert result.matched_invoice_id == "inv-001"
        assert result.matched_payment_id == "pay-001"
        assert result.recovered_amount == Decimal("20000.00")

    def test_worked_example_metrics(self) -> None:
        """Metrics show 100% recovery rate for the worked example."""
        from app.services.verification.metrics import CaseMetricsInput, compute_org_metrics

        cases = [
            CaseMetricsInput(
                case_id="case-001",
                organization_id="org-001",
                status="recovered",
                potential_leakage=Decimal("20000.00"),
                recovered_amount=Decimal("20000.00"),
            ),
        ]

        metrics = compute_org_metrics("org-001", cases)

        assert metrics.total_potential_leakage == Decimal("20000.00")
        assert metrics.total_recovered_revenue == Decimal("20000.00")
        assert metrics.recovery_rate == Decimal("1.000")
        assert metrics.recovered_cases == 1
        assert metrics.open_cases == 0


class TestPartialVerification:
    """Partial verification: invoice exists but unpaid → verified, not recovered."""

    def test_invoice_exists_unpaid(self) -> None:
        """Invoice found but no payment → status 'verified'."""
        now = time()
        today = date(2026, 8, 19)

        set_verification_data(
            cases={
                "case-002": CaseRecord(
                    case_id="case-002",
                    organization_id="org-001",
                    status="action_completed",
                    customer_id="cust-002",
                    potential_leakage=Decimal("5000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=now - 86400,
                ),
            },
            invoices={
                "inv-002": InvoiceRecord(
                    invoice_id="inv-002",
                    organization_id="org-001",
                    customer_id="cust-002",
                    total=Decimal("5000.00"),
                    outstanding_balance=Decimal("5000.00"),
                    status="sent",
                    created_at=now - 7200,
                ),
            },
            payments={},
        )

        executor = VerificationExecutor()
        result = executor.check("case-002", today=today)

        assert result.verified is True
        assert result.status == "verified"
        assert result.matched_invoice_id == "inv-002"
        assert result.matched_payment_id is None
        assert result.recovered_amount == Decimal("0")

    def test_later_payment_completes_recovery(self) -> None:
        """After payment arrives, verification transitions to 'recovered'."""
        now = time()
        today = date(2026, 8, 19)

        # First check: invoice exists, no payment
        set_verification_data(
            cases={
                "case-003": CaseRecord(
                    case_id="case-003",
                    organization_id="org-001",
                    status="verified",  # Already verified
                    customer_id="cust-003",
                    potential_leakage=Decimal("3000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=now - 172800,
                ),
            },
            invoices={
                "inv-003": InvoiceRecord(
                    invoice_id="inv-003",
                    organization_id="org-001",
                    customer_id="cust-003",
                    total=Decimal("3000.00"),
                    outstanding_balance=Decimal("3000.00"),
                    status="sent",
                    created_at=now - 86400,
                ),
            },
            payments={},
        )

        executor = VerificationExecutor()
        result = executor.check("case-003", today=today)
        assert result.status == "verified"
        assert result.recovered_amount == Decimal("0")

        # Now payment arrives
        set_verification_data(
            payments={
                "pay-003": PaymentRecord(
                    payment_id="pay-003",
                    organization_id="org-001",
                    customer_id="cust-003",
                    invoice_id="inv-003",
                    amount=Decimal("3000.00"),
                    payment_date=today,
                    created_at=now,
                ),
            },
        )

        result = executor.check("case-003", today=today)
        assert result.status == "recovered"
        assert result.recovered_amount == Decimal("3000.00")


class TestGracePeriod:
    """Grace period: no invoice after N days → needs_follow_up."""

    def test_no_invoice_within_grace_period(self) -> None:
        """No invoice within grace period → 'no_match' (still waiting)."""
        now = time()
        today = date(2026, 8, 19)

        set_verification_data(
            cases={
                "case-004": CaseRecord(
                    case_id="case-004",
                    organization_id="org-001",
                    status="action_completed",
                    customer_id="cust-004",
                    potential_leakage=Decimal("10000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=now - 86400,  # 1 day ago
                ),
            },
            invoices={},
            payments={},
        )

        executor = VerificationExecutor(grace_period_days=30)
        result = executor.check("case-004", today=today)

        assert result.status == "no_match"
        assert "No matching invoice" in result.message

    def test_no_invoice_past_grace_period(self) -> None:
        """No invoice past grace period → 'needs_follow_up'."""
        today = date(2026, 8, 19)
        # Compute timestamp relative to `today` so the grace-period calculation
        # is stable regardless of when the test runs.
        today_ts = calendar.timegm(today.timetuple())

        set_verification_data(
            cases={
                "case-005": CaseRecord(
                    case_id="case-005",
                    organization_id="org-001",
                    status="action_completed",
                    customer_id="cust-005",
                    potential_leakage=Decimal("8000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=today_ts - 2592000,  # 30 days before today
                ),
            },
            invoices={},
            payments={},
        )

        executor = VerificationExecutor(grace_period_days=30)
        result = executor.check("case-005", today=today)

        assert result.status == "needs_follow_up"
        assert "Follow-up required" in result.message

    def test_grace_period_boundary(self) -> None:
        """Exactly at grace period boundary → needs_follow_up."""
        today = date(2026, 8, 19)
        # Compute timestamp relative to `today` so the grace-period calculation
        # is stable regardless of when the test runs.
        today_ts = calendar.timegm(today.timetuple())

        set_verification_data(
            cases={
                "case-006": CaseRecord(
                    case_id="case-006",
                    organization_id="org-001",
                    status="action_completed",
                    customer_id="cust-006",
                    potential_leakage=Decimal("1000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=today_ts - (30 * 86400),  # exactly 30 days before today
                ),
            },
            invoices={},
            payments={},
        )

        executor = VerificationExecutor(grace_period_days=30)
        result = executor.check("case-006", today=today)

        assert result.status == "needs_follow_up"


class TestAmountTolerance:
    """Amount tolerance matching."""

    def test_exact_match(self) -> None:
        """Exact amount match → verified."""
        now = time()
        set_verification_data(
            cases={
                "case-007": CaseRecord(
                    case_id="case-007",
                    organization_id="org-001",
                    status="action_completed",
                    customer_id="cust-007",
                    potential_leakage=Decimal("1000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=now - 86400,
                ),
            },
            invoices={
                "inv-007": InvoiceRecord(
                    invoice_id="inv-007",
                    organization_id="org-001",
                    customer_id="cust-007",
                    total=Decimal("1000.00"),
                    outstanding_balance=Decimal("1000.00"),
                    status="sent",
                    created_at=now - 7200,
                ),
            },
        )

        executor = VerificationExecutor()
        result = executor.check("case-007")
        assert result.status == "verified"
        assert result.matched_invoice_id == "inv-007"

    def test_within_tolerance(self) -> None:
        """Amount within 1% tolerance → matched."""
        now = time()
        set_verification_data(
            cases={
                "case-008": CaseRecord(
                    case_id="case-008",
                    organization_id="org-001",
                    status="action_completed",
                    customer_id="cust-008",
                    potential_leakage=Decimal("10000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=now - 86400,
                ),
            },
            invoices={
                "inv-008": InvoiceRecord(
                    invoice_id="inv-008",
                    organization_id="org-001",
                    customer_id="cust-008",
                    total=Decimal("10050.00"),  # 0.5% difference
                    outstanding_balance=Decimal("10050.00"),
                    status="sent",
                    created_at=now - 7200,
                ),
            },
        )

        executor = VerificationExecutor(amount_tolerance=Decimal("0.01"))
        result = executor.check("case-008")
        assert result.status == "verified"

    def test_outside_tolerance(self) -> None:
        """Amount outside tolerance → no match."""
        now = time()
        set_verification_data(
            cases={
                "case-009": CaseRecord(
                    case_id="case-009",
                    organization_id="org-001",
                    status="action_completed",
                    customer_id="cust-009",
                    potential_leakage=Decimal("10000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=now - 86400,
                ),
            },
            invoices={
                "inv-009": InvoiceRecord(
                    invoice_id="inv-009",
                    organization_id="org-001",
                    customer_id="cust-009",
                    total=Decimal("10200.00"),  # 2% difference
                    outstanding_balance=Decimal("10200.00"),
                    status="sent",
                    created_at=now - 7200,
                ),
            },
        )

        executor = VerificationExecutor(amount_tolerance=Decimal("0.01"))
        result = executor.check("case-009")
        assert result.status == "no_match"


class TestCrossTenantIsolation:
    """Cross-tenant isolation for verification."""

    def test_org_a_cannot_see_org_b_invoices(self) -> None:
        """Org A's case doesn't match Org B's invoice."""
        now = time()
        set_verification_data(
            cases={
                "case-010": CaseRecord(
                    case_id="case-010",
                    organization_id="org-A",
                    status="action_completed",
                    customer_id="cust-A1",
                    potential_leakage=Decimal("5000.00"),
                    action_type="create_invoice_draft",
                    action_completed_at=now - 86400,
                ),
            },
            invoices={
                "inv-B1": InvoiceRecord(
                    invoice_id="inv-B1",
                    organization_id="org-B",
                    customer_id="cust-B1",
                    total=Decimal("5000.00"),
                    outstanding_balance=Decimal("5000.00"),
                    status="sent",
                    created_at=now - 7200,
                ),
            },
        )

        executor = VerificationExecutor()
        result = executor.check("case-010")
        assert result.status == "no_match"
        assert result.matched_invoice_id is None


class TestEdgeCases:
    """Edge cases."""

    def test_nonexistent_case(self) -> None:
        """Nonexistent case returns no_match."""
        executor = VerificationExecutor()
        result = executor.check("nonexistent")
        assert result.status == "no_match"
        assert "not found" in result.message

    def test_wrong_status_not_checked(self) -> None:
        """Case in wrong status is not checked."""
        time()
        set_verification_data(
            cases={
                "case-011": CaseRecord(
                    case_id="case-011",
                    organization_id="org-001",
                    status="pending_review",  # Not action_completed
                    potential_leakage=Decimal("1000.00"),
                ),
            },
        )

        executor = VerificationExecutor()
        result = executor.check("case-011")
        assert result.status == "no_match"
        assert "must be" in result.message

    def test_non_invoice_action_type(self) -> None:
        """Non-invoice action type gets needs_follow_up."""
        now = time()
        set_verification_data(
            cases={
                "case-012": CaseRecord(
                    case_id="case-012",
                    organization_id="org-001",
                    status="action_completed",
                    potential_leakage=Decimal("1000.00"),
                    action_type="send_payment_reminder",
                    action_completed_at=now - 86400,
                ),
            },
        )

        executor = VerificationExecutor()
        result = executor.check("case-012")
        assert result.status == "needs_follow_up"
        assert "manual verification" in result.message


def time() -> float:
    """Get current timestamp."""
    import time as _time

    return _time.time()
