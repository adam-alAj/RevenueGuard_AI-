"""Underbilling rule.

Detects: sum(ContractLine.quantity x unit_price) vs
sum(InvoiceLine.quantity x unit_price) for linked records, where
the difference exceeds a configured threshold.

Parameters:
- amount_threshold: minimum dollar difference to flag (default: 100.00)
- percentage_threshold: minimum percentage difference to flag (default: 5.0 = 5%)
"""

from __future__ import annotations

from decimal import Decimal

from app.rules.base import BaseRule, LeakageFinding, RuleContext


class UnderbillingRule(BaseRule):
    leakage_type = "underbilling"
    name = "Underbilling"
    description = "Invoiced amount is less than contracted amount beyond threshold"
    default_parameters = {"amount_threshold": 100.00, "percentage_threshold": 5.0}

    def evaluate(self, ctx: RuleContext) -> list[LeakageFinding]:
        findings: list[LeakageFinding] = []
        amount_threshold = ctx.get_decimal_param("amount_threshold", Decimal("100"))
        pct_threshold = Decimal(str(ctx.get_param("percentage_threshold", 5.0)))

        # Group contract lines by contract_id
        contract_expected: dict[str, Decimal] = {}
        for cl in ctx.contract_lines:
            cid = str(cl["contract_id"])
            amount = Decimal(str(cl["quantity"])) * Decimal(str(cl["unit_price"]))
            contract_expected[cid] = contract_expected.get(cid, Decimal("0")) + amount

        # Group invoice lines by contract_id (via invoice's contract_id)
        contract_actual: dict[str, Decimal] = {}
        invoice_by_id = {str(inv["id"]): inv for inv in ctx.invoices}
        for il in ctx.invoice_lines:
            inv = invoice_by_id.get(str(il["invoice_id"]))
            if inv and inv.get("contract_id"):
                cid = str(inv["contract_id"])
                amount = Decimal(str(il["quantity"])) * Decimal(str(il["unit_price"]))
                contract_actual[cid] = contract_actual.get(cid, Decimal("0")) + amount

        # Compare for each contract
        for contract in ctx.contracts:
            cid = str(contract["id"])
            expected = contract_expected.get(cid, Decimal("0"))
            actual = contract_actual.get(cid, Decimal("0"))

            if expected == 0:
                continue

            difference = expected - actual
            if difference <= 0:
                continue  # Not underbilling (might be overbilling)

            # Check thresholds
            if difference < amount_threshold:
                continue
            pct_diff = (difference / expected) * 100
            if pct_diff < pct_threshold:
                continue

            findings.append(
                LeakageFinding(
                    leakage_type=self.leakage_type,
                    description=(
                        f"Contract '{contract.get('name', 'Unknown')}': "
                        f"expected ${expected:.2f}, invoiced ${actual:.2f}, "
                        f"difference ${difference:.2f} ({pct_diff:.1f}%)"
                    ),
                    expected_amount=expected,
                    actual_amount=actual,
                    potential_leakage=difference,
                    customer_id=contract.get("customer_id"),
                    contract_id=contract["id"],
                )
            )

        return findings
