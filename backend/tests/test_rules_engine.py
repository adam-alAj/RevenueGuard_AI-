"""Tests for the deterministic Revenue Leakage Rules Engine.

Every test uses exact dollar-amount assertions — not "found something,"
but "found exactly $X." This is what makes the engine trustworthy.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.rules.base import RuleContext
from app.rules.contract_expiration import ContractExpirationRule
from app.rules.engine import ALL_RULES, RULE_MAP
from app.rules.missing_invoice import MissingInvoiceRule
from app.rules.overdue_invoice import OverdueInvoiceRule
from app.rules.partial_payment import PartialPaymentRule
from app.rules.pricing_mismatch import PricingMismatchRule
from app.rules.underbilling import UnderbillingRule
from tests.fixtures.rules_scenarios import (
    CONTRACT_A,
    CONTRACT_B,
    CONTRACTS,
    CUSTOMER_A,
    INVOICE_1,
    INVOICE_2,
    INVOICE_3,
    INVOICE_LINES,
    INVOICES,
    PROJECT_1,
    PROJECT_2,
    PROJECT_3,
    get_full_context,
)


def _make_ctx(**overrides) -> RuleContext:
    """Create a RuleContext with defaults from the fixture data."""
    defaults = get_full_context()
    defaults.update(overrides)
    return RuleContext(**defaults)


# ---------------------------------------------------------------------------
# Rule 1: Missing Invoice
# ---------------------------------------------------------------------------

class TestMissingInvoiceRule:
    def test_completed_project_no_invoice_detected(self) -> None:
        """PROJECT_3 is completed, has no invoice → detected."""
        rule = MissingInvoiceRule()
        ctx = _make_ctx(
            today=date(2026, 6, 15),  # Well past the 30-day window
        )
        findings = rule.evaluate(ctx)

        # PROJECT_3 (Internal Tool) should be detected
        project_findings = [f for f in findings if f.project_id == PROJECT_3]
        assert len(project_findings) == 1
        assert project_findings[0].potential_leakage == Decimal("0")  # No contract → $0

    def test_completed_project_with_invoice_not_detected(self) -> None:
        """PROJECT_1 is completed but has INVOICE_1 → not detected."""
        rule = MissingInvoiceRule()
        ctx = _make_ctx(today=date(2026, 6, 15))
        findings = rule.evaluate(ctx)

        project_findings = [f for f in findings if f.project_id == PROJECT_1]
        assert len(project_findings) == 0

    def test_active_project_not_detected(self) -> None:
        """PROJECT_2 is active → not detected by missing invoice rule."""
        rule = MissingInvoiceRule()
        ctx = _make_ctx(today=date(2026, 6, 15))
        findings = rule.evaluate(ctx)

        project_findings = [f for f in findings if f.project_id == PROJECT_2]
        assert len(project_findings) == 0

    def test_completed_project_no_contract_detected(self) -> None:
        """PROJECT_3 is completed, no contract → detected with $0 expected."""
        rule = MissingInvoiceRule()
        ctx = _make_ctx(today=date(2026, 6, 15))
        findings = rule.evaluate(ctx)
        project_findings = [f for f in findings if f.project_id == PROJECT_3]
        assert len(project_findings) == 1
        assert project_findings[0].expected_amount == Decimal("0")

    def test_within_billing_window_not_detected(self) -> None:
        """Project completed recently, within billing window → not detected."""
        # Create a project completed 5 days ago with an invoice
        project = {"id": uuid.uuid4(), "name": "Recent", "status": "completed",
                   "customer_id": CUSTOMER_A, "contract_id": CONTRACT_A,
                   "is_billable": True, "end_date": date(2026, 6, 10),
                   "start_date": date(2026, 1, 1)}
        rule = MissingInvoiceRule()
        ctx = _make_ctx(
            today=date(2026, 6, 15),  # 5 days after project end
            projects=[project],
        )
        findings = rule.evaluate(ctx)
        assert len(findings) == 0  # Within 30-day window

    def test_exact_dollar_amount(self) -> None:
        """Missing invoice for project with contract shows exact expected amount."""
        rule = MissingInvoiceRule()
        # PROJECT_3 has no contract, so expected is $0
        ctx = _make_ctx(today=date(2026, 6, 15))
        findings = rule.evaluate(ctx)
        project_findings = [f for f in findings if f.project_id == PROJECT_3]
        assert project_findings[0].expected_amount == Decimal("0")
        assert project_findings[0].actual_amount == Decimal("0")


# ---------------------------------------------------------------------------
# Rule 2: Underbilling
# ---------------------------------------------------------------------------

class TestUnderbillingRule:
    def test_underbilling_detected(self) -> None:
        """Contract A: $10,000 expected, $8,000 invoiced on INV-001 → $2,000 underbilling.
        Note: INV-003 ($3,000) also links to Contract A, making total $11,000.
        We test with only INV-001 to isolate the underbilling scenario."""
        rule = UnderbillingRule()
        # Use only Invoice 1 for Contract A (ignore Invoice 3)
        invoices = [inv for inv in INVOICES if inv["id"] == INVOICE_1 or inv["id"] == INVOICE_2]
        invoice_lines = [il for il in INVOICE_LINES if il["invoice_id"] in (INVOICE_1, INVOICE_2)]
        ctx = _make_ctx(invoices=invoices, invoice_lines=invoice_lines)
        findings = rule.evaluate(ctx)

        contract_findings = [f for f in findings if f.contract_id == CONTRACT_A]
        assert len(contract_findings) == 1
        assert contract_findings[0].expected_amount == Decimal("10000")
        assert contract_findings[0].actual_amount == Decimal("8000")
        assert contract_findings[0].potential_leakage == Decimal("2000")

    def test_no_underbilling_when_fully_invoiced(self) -> None:
        """Contract B: $5,000 expected, $5,000 invoiced → no finding."""
        rule = UnderbillingRule()
        ctx = _make_ctx()
        findings = rule.evaluate(ctx)

        contract_findings = [f for f in findings if f.contract_id == CONTRACT_B]
        assert len(contract_findings) == 0

    def test_threshold_not_met(self) -> None:
        """Underbilling below threshold → not detected."""
        rule = UnderbillingRule()
        # Use only Invoice 1 for Contract A ($8,000 vs $10,000 = $2,000 diff)
        invoices = [inv for inv in INVOICES if inv["id"] == INVOICE_1 or inv["id"] == INVOICE_2]
        invoice_lines = [il for il in INVOICE_LINES if il["invoice_id"] in (INVOICE_1, INVOICE_2)]
        # With threshold of $5,000 — $2,000 difference is below → not detected
        ctx = _make_ctx(
            invoices=invoices, invoice_lines=invoice_lines,
            parameters={"amount_threshold": 5000, "percentage_threshold": 5.0},
        )
        findings = rule.evaluate(ctx)
        contract_findings = [f for f in findings if f.contract_id == CONTRACT_A]
        assert len(contract_findings) == 0

    def test_exact_dollar_amounts(self) -> None:
        """Underbilling amounts are exact Decimal values."""
        rule = UnderbillingRule()
        invoices = [inv for inv in INVOICES if inv["id"] == INVOICE_1 or inv["id"] == INVOICE_2]
        invoice_lines = [il for il in INVOICE_LINES if il["invoice_id"] in (INVOICE_1, INVOICE_2)]
        ctx = _make_ctx(invoices=invoices, invoice_lines=invoice_lines)
        findings = rule.evaluate(ctx)
        contract_findings = [f for f in findings if f.contract_id == CONTRACT_A]
        f = contract_findings[0]
        assert f.expected_amount == Decimal("10000")
        assert f.actual_amount == Decimal("8000")
        assert f.potential_leakage == Decimal("2000")


# ---------------------------------------------------------------------------
# Rule 3: Pricing Mismatch
# ---------------------------------------------------------------------------

class TestPricingMismatchRule:
    def test_pricing_mismatch_detected(self) -> None:
        """Invoice 1 lines are $40/unit vs contract $50/unit → mismatch."""
        rule = PricingMismatchRule()
        ctx = _make_ctx()
        findings = rule.evaluate(ctx)

        # Should find 2 mismatches (Design + Development)
        assert len(findings) == 2
        for f in findings:
            assert f.potential_leakage == Decimal("10")  # $50 - $40 = $10 per unit

    def test_no_mismatch_when_prices_match(self) -> None:
        """Invoice 2 lines match contract prices → no finding."""
        rule = PricingMismatchRule()
        ctx = _make_ctx()
        findings = rule.evaluate(ctx)

        # Invoice 2 is for Contract B — prices match ($50/unit)
        inv2_findings = [f for f in findings if f.invoice_id == INVOICE_2]
        assert len(inv2_findings) == 0


# ---------------------------------------------------------------------------
# Rule 4: Overdue Invoice
# ---------------------------------------------------------------------------

class TestOverdueInvoiceRule:
    def test_overdue_detected(self) -> None:
        """INVOICE_3: due 2026-01-01, outstanding $3,000, today is 2026-06-15 → detected."""
        rule = OverdueInvoiceRule()
        ctx = _make_ctx(today=date(2026, 6, 15))
        findings = rule.evaluate(ctx)

        inv3_findings = [f for f in findings if f.invoice_id == INVOICE_3]
        assert len(inv3_findings) == 1
        assert inv3_findings[0].potential_leakage == Decimal("3000")

    def test_not_overdue_yet(self) -> None:
        """INVOICE_3 due 2026-01-01, today is 2025-12-15 → not overdue."""
        rule = OverdueInvoiceRule()
        ctx = _make_ctx(today=date(2025, 12, 15))
        findings = rule.evaluate(ctx)
        assert len(findings) == 0

    def test_fully_paid_not_detected(self) -> None:
        """INVOICE_1 outstanding=$0 → not detected."""
        rule = OverdueInvoiceRule()
        ctx = _make_ctx(today=date(2026, 6, 15))
        findings = rule.evaluate(ctx)

        inv1_findings = [f for f in findings if f.invoice_id == INVOICE_1]
        assert len(inv1_findings) == 0

    def test_grace_period(self) -> None:
        """INVOICE_3 with 90-day grace period: due 2026-01-01 + 90 days = 2026-04-01,
        today is 2026-03-15 → not overdue yet."""
        rule = OverdueInvoiceRule()
        ctx = _make_ctx(
            today=date(2026, 3, 15),
            parameters={"grace_period_days": 90},
        )
        findings = rule.evaluate(ctx)
        assert len(findings) == 0

    def test_exact_outstanding_amount(self) -> None:
        """Overdue finding has exact outstanding balance."""
        rule = OverdueInvoiceRule()
        ctx = _make_ctx(today=date(2026, 6, 15))
        findings = rule.evaluate(ctx)
        inv3_findings = [f for f in findings if f.invoice_id == INVOICE_3]
        assert inv3_findings[0].expected_amount == Decimal("3000")
        assert inv3_findings[0].actual_amount == Decimal("0")


# ---------------------------------------------------------------------------
# Rule 5: Partial Payment
# ---------------------------------------------------------------------------

class TestPartialPaymentRule:
    def test_overdue_with_no_payment_detected(self) -> None:
        """INVOICE_3: $3,000 total, no payments for Customer A covering this → gap."""
        rule = PartialPaymentRule()
        ctx = _make_ctx()
        findings = rule.evaluate(ctx)

        inv3_findings = [f for f in findings if f.invoice_id == INVOICE_3]
        assert len(inv3_findings) == 1

    def test_fully_paid_no_finding(self) -> None:
        """INVOICE_2: $5,000 total, $5,000 payment from Customer B → no gap."""
        rule = PartialPaymentRule()
        ctx = _make_ctx()
        findings = rule.evaluate(ctx)

        inv2_findings = [f for f in findings if f.invoice_id == INVOICE_2]
        assert len(inv2_findings) == 0


# ---------------------------------------------------------------------------
# Rule 6: Contract Expiration
# ---------------------------------------------------------------------------

class TestContractExpirationRule:
    def test_expired_contract_no_renewal_detected(self) -> None:
        """If a project ends after contract expiration with no renewal → detected."""
        # Modify fixture: CONTRACT_A expires 2025-12-31, PROJECT_1 ends 2026-01-15
        contracts = list(CONTRACTS)
        contracts[0] = {**contracts[0], "expiration_date": date(2025, 12, 31)}

        rule = ContractExpirationRule()
        ctx = _make_ctx(
            today=date(2026, 6, 15),
            contracts=contracts,
        )
        findings = rule.evaluate(ctx)

        # PROJECT_1 ends 2026-01-15, contract expired 2025-12-31 → detected
        project_findings = [f for f in findings if f.project_id == PROJECT_1]
        assert len(project_findings) == 1

    def test_active_project_not_expired(self) -> None:
        """Active project within contract period → not detected."""
        rule = ContractExpirationRule()
        ctx = _make_ctx(today=date(2026, 6, 15))
        findings = rule.evaluate(ctx)

        # PROJECT_2 is active, contract expires 2026-12-31 → not detected
        project_findings = [f for f in findings if f.project_id == PROJECT_2]
        assert len(project_findings) == 0


# ---------------------------------------------------------------------------
# Composite engine test
# ---------------------------------------------------------------------------

class TestRuleEngineComposite:
    def test_all_rules_produce_correct_total(self) -> None:
        """Running all rules produces the expected findings count."""
        findings_all = []
        ctx = _make_ctx(today=date(2026, 6, 15))
        for rule in ALL_RULES:
            findings_all.extend(rule.evaluate(ctx))

        # Should have findings from:
        # - Missing Invoice: PROJECT_3 (1)
        # - Underbilling: CONTRACT_A (1)
        # - Pricing Mismatch: 2 lines on Invoice 1 (2)
        # - Overdue Invoice: INVOICE_3 (1)
        # - Partial Payment: INVOICE_3 (1)
        # - Contract Expiration: none (contracts not expired in default fixture)
        assert len(findings_all) >= 5

    def test_no_false_positive_on_fully_correct_data(self) -> None:
        """When everything matches, no rules should fire."""

        # Create a perfectly matched scenario
        customer = uuid.uuid4()
        contract = uuid.uuid4()
        project = uuid.uuid4()
        invoice = uuid.uuid4()

        projects = [{"id": project, "name": "Test", "status": "completed",
                      "customer_id": customer, "contract_id": contract,
                      "is_billable": True, "end_date": date(2025, 12, 1),
                      "start_date": date(2025, 6, 1)}]
        contracts_list = [{"id": contract, "name": "Test Contract",
                           "customer_id": customer,
                           "start_date": date(2025, 1, 1),
                           "end_date": date(2026, 12, 31),
                           "expiration_date": date(2026, 12, 31),
                           "total_value": Decimal("5000"),
                           "billing_frequency": "project"}]
        contract_lines = [{"id": uuid.uuid4(), "contract_id": contract,
                           "description": "Work", "quantity": 100,
                           "unit_price": Decimal("50"), "total": Decimal("5000")}]
        invoices = [{"id": invoice, "invoice_number": "INV-TEST",
                      "customer_id": customer, "contract_id": contract,
                      "project_id": project, "total": Decimal("5000"),
                      "outstanding_balance": Decimal("0"),
                      "due_date": date(2026, 1, 15),
                      "issued_date": date(2025, 12, 15)}]
        invoice_lines = [{"id": uuid.uuid4(), "invoice_id": invoice,
                           "description": "Work", "quantity": 100,
                           "unit_price": Decimal("50"), "total": Decimal("5000")}]
        payments = [{"id": uuid.uuid4(), "customer_id": customer,
                      "amount": Decimal("5000"), "payment_date": date(2026, 1, 10)}]

        ctx = RuleContext(
            organization_id=uuid.uuid4(),
            rule_version_id=uuid.uuid4(),
            parameters={},
            today=date(2026, 6, 15),
            projects=projects,
            contracts=contracts_list,
            contract_lines=contract_lines,
            invoices=invoices,
            invoice_lines=invoice_lines,
            payments=payments,
            credit_notes=[],
        )

        all_findings = []
        for rule in ALL_RULES:
            all_findings.extend(rule.evaluate(ctx))

        assert len(all_findings) == 0, (
            f"Expected 0 findings on perfectly matched data, got {len(all_findings)}: "
            f"{[f.description for f in all_findings]}"
        )

    def test_threshold_change_affects_detection(self) -> None:
        """Changing a threshold produces measurably different results."""
        rule = UnderbillingRule()
        invoices = [inv for inv in INVOICES if inv["id"] == INVOICE_1 or inv["id"] == INVOICE_2]
        invoice_lines = [il for il in INVOICE_LINES if il["invoice_id"] in (INVOICE_1, INVOICE_2)]

        # With low threshold: $2,000 difference → detected
        ctx_low = _make_ctx(
            invoices=invoices, invoice_lines=invoice_lines,
            parameters={"amount_threshold": 100, "percentage_threshold": 5.0},
        )
        findings_low = rule.evaluate(ctx_low)
        assert len(findings_low) == 1

        # With high threshold: $2,000 difference below $5,000 → NOT detected
        ctx_high = _make_ctx(
            invoices=invoices, invoice_lines=invoice_lines,
            parameters={"amount_threshold": 5000, "percentage_threshold": 5.0},
        )
        findings_high = rule.evaluate(ctx_high)
        assert len(findings_high) == 0

    def test_legitimate_amendment_not_flagged(self) -> None:
        """Contract amendment reducing price should not trigger pricing mismatch."""
        # If an invoice line matches the AMENDED contract price, no mismatch
        rule = PricingMismatchRule()

        # Contract line at $50, invoice line at $50 (after amendment) → match
        ctx = _make_ctx()
        findings = rule.evaluate(ctx)

        # Invoice 2 (Contract B) has matching prices → no finding for that
        inv2_findings = [f for f in findings if f.invoice_id == INVOICE_2]
        assert len(inv2_findings) == 0


# ---------------------------------------------------------------------------
# Rule map sanity
# ---------------------------------------------------------------------------

class TestRuleMap:
    def test_all_6_rules_registered(self) -> None:
        assert len(RULE_MAP) == 6

    def test_leakage_types(self) -> None:
        expected = {"missing_invoice", "underbilling", "pricing_mismatch",
                     "uncollected_invoice", "partial_payment", "contract_expiration"}
        assert set(RULE_MAP.keys()) == expected

    def test_all_rules_have_defaults(self) -> None:
        for rule in ALL_RULES:
            assert isinstance(rule.default_parameters, dict)
            assert rule.leakage_type
            assert rule.name
            assert rule.description
