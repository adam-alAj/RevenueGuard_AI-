"""Verification executor — checks whether completed actions resulted in recovered revenue.

For create_invoice_draft actions:
1. Look for a new Invoice linked to the same customer/contract with an amount
   matching (within tolerance) case.potential_leakage, created after the action
2. If found, check for a linked Payment fully covering it
3. If invoice exists but unpaid → "verified" (not yet recovered)
4. If payment fully covers → "recovered"
5. If no invoice after grace period → "needs_follow_up"

For other action types:
- Check if the case status has progressed (simplified verification)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

# Default tolerance for amount matching (0.01 = 1%)
DEFAULT_AMOUNT_TOLERANCE = Decimal("0.01")

# Default grace period in days
DEFAULT_GRACE_PERIOD_DAYS = 30


@dataclass
class VerificationResult:
    """Result of a case verification check."""

    case_id: str
    verified: bool
    status: str  # "verified", "recovered", "needs_follow_up", "no_match"
    matched_invoice_id: str | None = None
    matched_payment_id: str | None = None
    recovered_amount: Decimal | None = None
    message: str = ""
    checked_at: float = field(default_factory=time.time)


@dataclass
class InvoiceRecord:
    """In-memory invoice record for verification."""

    invoice_id: str
    organization_id: str
    customer_id: str
    contract_id: str | None = None
    total: Decimal = Decimal("0")
    outstanding_balance: Decimal = Decimal("0")
    status: str = "draft"
    issued_date: date | None = None
    created_at: float = 0.0


@dataclass
class PaymentRecord:
    """In-memory payment record for verification."""

    payment_id: str
    organization_id: str
    customer_id: str
    invoice_id: str | None = None
    amount: Decimal = Decimal("0")
    payment_date: date | None = None
    created_at: float = 0.0


@dataclass
class CaseRecord:
    """In-memory case record for verification."""

    case_id: str
    organization_id: str
    status: str = "detected"
    customer_id: str | None = None
    contract_id: str | None = None
    potential_leakage: Decimal = Decimal("0")
    action_type: str | None = None
    action_completed_at: float | None = None
    recovered_amount: Decimal = Decimal("0")


# In-memory data stores (will be replaced with DB queries in production)
_invoice_store: dict[str, InvoiceRecord] = {}
_payment_store: dict[str, PaymentRecord] = {}
_case_store: dict[str, CaseRecord] = {}
_verification_results: dict[str, VerificationResult] = {}


def set_verification_data(
    cases: dict[str, CaseRecord] | None = None,
    invoices: dict[str, InvoiceRecord] | None = None,
    payments: dict[str, PaymentRecord] | None = None,
) -> None:
    """Set data stores for testing."""
    global _case_store, _invoice_store, _payment_store
    if cases is not None:
        _case_store = cases
    if invoices is not None:
        _invoice_store = invoices
    if payments is not None:
        _payment_store = payments


def clear_verification_data() -> None:
    """Clear all verification data stores."""
    global _case_store, _invoice_store, _payment_store, _verification_results
    _case_store = {}
    _invoice_store = {}
    _payment_store = {}
    _verification_results = {}


def get_verification_result(case_id: str) -> VerificationResult | None:
    """Get the last verification result for a case."""
    return _verification_results.get(case_id)


class VerificationExecutor:
    """Checks whether completed actions resulted in recovered revenue.

    Verification is deterministic — no LLM involvement. It matches
    invoice and payment data against the case's expected recovery amount.
    """

    def __init__(
        self,
        amount_tolerance: Decimal = DEFAULT_AMOUNT_TOLERANCE,
        grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS,
    ) -> None:
        self.amount_tolerance = amount_tolerance
        self.grace_period_days = grace_period_days

    def check(
        self,
        case_id: str,
        today: date | None = None,
    ) -> VerificationResult:
        """Verify whether a completed case has actually resulted in recovery.

        Args:
            case_id: UUID of the case to verify.
            today: Current date for grace period calculation.

        Returns:
            VerificationResult with the verification outcome.
        """
        if today is None:
            today = date.today()

        case = _case_store.get(case_id)
        if not case:
            return VerificationResult(
                case_id=case_id,
                verified=False,
                status="no_match",
                message=f"Case not found: {case_id}",
            )

        # Only verify cases in action_completed or verified status
        if case.status not in ("action_completed", "verified"):
            return VerificationResult(
                case_id=case_id,
                verified=False,
                status="no_match",
                message=f"Case status is '{case.status}', must be 'action_completed' or 'verified'.",
            )

        # For create_invoice_draft actions, check for invoice + payment
        if case.action_type == "create_invoice_draft":
            return self._check_invoice_recovery(case, today)

        # For other action types, simplified verification
        return self._check_other_action(case)

    def _check_invoice_recovery(self, case: CaseRecord, today: date) -> VerificationResult:
        """Check for invoice recovery for create_invoice_draft actions."""
        # Look for matching invoices
        matching_invoices = self._find_matching_invoices(case)

        if not matching_invoices:
            # No invoice found — check grace period
            if case.action_completed_at:
                days_since = (today - date.fromtimestamp(case.action_completed_at)).days
                if days_since >= self.grace_period_days:
                    return VerificationResult(
                        case_id=case.case_id,
                        verified=False,
                        status="needs_follow_up",
                        message=(
                            f"No matching invoice found after {days_since} days "
                            f"(grace period: {self.grace_period_days} days). "
                            f"Follow-up required."
                        ),
                    )

            return VerificationResult(
                case_id=case.case_id,
                verified=False,
                status="no_match",
                message="No matching invoice found yet.",
            )

        # Found matching invoice — check for payment
        best_invoice = matching_invoices[0]
        payment = self._find_matching_payment(case, best_invoice)

        if payment:
            # Fully recovered
            recovered = min(payment.amount, case.potential_leakage)
            result = VerificationResult(
                case_id=case.case_id,
                verified=True,
                status="recovered",
                matched_invoice_id=best_invoice.invoice_id,
                matched_payment_id=payment.payment_id,
                recovered_amount=recovered,
                message=(
                    f"Invoice {best_invoice.invoice_id} matched and paid. "
                    f"Recovered: ${recovered:.2f}"
                ),
            )
        else:
            # Invoice exists but unpaid — partial verification
            result = VerificationResult(
                case_id=case.case_id,
                verified=True,
                status="verified",
                matched_invoice_id=best_invoice.invoice_id,
                recovered_amount=Decimal("0"),
                message=(
                    f"Invoice {best_invoice.invoice_id} found but not yet paid. Awaiting payment."
                ),
            )

        _verification_results[case.case_id] = result
        return result

    def _check_other_action(self, case: CaseRecord) -> VerificationResult:
        """Simplified verification for non-invoice actions."""
        # For non-invoice actions, we can't automatically verify recovery
        # The case stays in action_completed until manually verified
        return VerificationResult(
            case_id=case.case_id,
            verified=False,
            status="needs_follow_up",
            message=(
                f"Action type '{case.action_type}' requires manual verification. "
                f"Automatic verification is only available for create_invoice_draft."
            ),
        )

    def _find_matching_invoices(self, case: CaseRecord) -> list[InvoiceRecord]:
        """Find invoices matching the case's customer/contract and amount."""
        matches = []
        for inv in _invoice_store.values():
            if inv.organization_id != case.organization_id:
                continue
            if case.customer_id and inv.customer_id != case.customer_id:
                continue
            if case.contract_id and inv.contract_id != case.contract_id:
                continue

            # Check amount match within tolerance
            if case.potential_leakage > 0:
                diff = abs(inv.total - case.potential_leakage)
                tolerance = case.potential_leakage * self.amount_tolerance
                if diff > tolerance:
                    continue

            # Invoice must be created after the action
            if case.action_completed_at and inv.created_at < case.action_completed_at:
                continue

            matches.append(inv)

        # Sort by created_at descending (most recent first)
        matches.sort(key=lambda x: x.created_at, reverse=True)
        return matches

    def _find_matching_payment(
        self, case: CaseRecord, invoice: InvoiceRecord
    ) -> PaymentRecord | None:
        """Find a payment that covers the invoice."""
        for payment in _payment_store.values():
            if payment.organization_id != case.organization_id:
                continue
            if payment.customer_id != case.customer_id:
                continue
            if payment.invoice_id != invoice.invoice_id:
                continue
            # Payment must cover at least the invoice amount
            if payment.amount >= invoice.total:
                return payment
        return None

    def check_all_for_org(
        self,
        organization_id: str,
        today: date | None = None,
    ) -> list[VerificationResult]:
        """Check all action_completed/verified cases in an organization.

        Used after ingestion to auto-verify cases.
        """
        results = []
        for case in _case_store.values():
            if case.organization_id != organization_id:
                continue
            if case.status in ("action_completed", "verified"):
                result = self.check(case.case_id, today)
                results.append(result)
        return results
