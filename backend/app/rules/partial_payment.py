"""Partial Payment Discrepancy rule.

Detects: sum(payments allocated to invoice) < Invoice.total AND
no linked CreditNote explains the gap.

A partial payment discrepancy is any invoice with:
1. A positive outstanding balance (not fully paid)
2. No credit notes that would explain the remaining balance

This means the customer owes money and there's no documented reason
for the shortfall (e.g. a disputed charge, a write-off, etc.).
"""

from __future__ import annotations

from decimal import Decimal

from app.rules.base import BaseRule, LeakageFinding, RuleContext


class PartialPaymentRule(BaseRule):
    leakage_type = "partial_payment"
    name = "Partial Payment Discrepancy"
    description = "Invoice total exceeds payments with no explaining credit note"
    default_parameters = {}

    def evaluate(self, ctx: RuleContext) -> list[LeakageFinding]:
        findings = []

        # Group credit notes by invoice_id
        cn_by_invoice: dict[str, list] = {}
        for cn in ctx.credit_notes:
            inv_id = cn.get("invoice_id")
            if inv_id:
                cn_by_invoice.setdefault(str(inv_id), []).append(cn)

        for invoice in ctx.invoices:
            inv_total = Decimal(str(invoice.get("total", 0)))
            if inv_total <= 0:
                continue

            outstanding = Decimal(str(invoice.get("outstanding_balance", 0)))
            if outstanding <= 0:
                continue  # Fully paid — no discrepancy

            # Check if credit notes explain the outstanding balance
            inv_id = str(invoice["id"])
            credit_note_total = sum(
                Decimal(str(cn["amount"])) for cn in cn_by_invoice.get(inv_id, [])
            )

            # If credit notes cover the outstanding balance, no discrepancy
            if credit_note_total >= outstanding:
                continue

            # There's an unexplained partial payment discrepancy
            discrepancy = outstanding - credit_note_total

            findings.append(
                LeakageFinding(
                    leakage_type=self.leakage_type,
                    description=(
                        f"Invoice '{invoice.get('invoice_number', 'Unknown')}': "
                        f"total ${inv_total:.2f}, outstanding ${outstanding:.2f}, "
                        f"credit notes ${credit_note_total:.2f}, "
                        f"unexplained gap ${discrepancy:.2f}"
                    ),
                    expected_amount=inv_total,
                    actual_amount=inv_total - outstanding,
                    potential_leakage=discrepancy,
                    customer_id=invoice.get("customer_id"),
                    contract_id=invoice.get("contract_id"),
                    invoice_id=invoice["id"],
                )
            )

        return findings
