"""Overdue Invoice rule.

Detects: invoice.due_date < today AND invoice.outstanding_balance > 0.

Parameters:
- grace_period_days: extra days after due date before flagging (default: 0)
"""

from __future__ import annotations

from decimal import Decimal

from app.rules.base import BaseRule, LeakageFinding, RuleContext


class OverdueInvoiceRule(BaseRule):
    leakage_type = "overdue_invoice"
    name = "Overdue Invoice"
    description = "Invoice past due date with outstanding balance"
    default_parameters = {"grace_period_days": 0}

    def evaluate(self, ctx: RuleContext) -> list[LeakageFinding]:
        findings = []
        grace_days = ctx.get_param("grace_period_days", 0)

        for invoice in ctx.invoices:
            due_date = invoice.get("due_date")
            if not due_date:
                continue

            outstanding = Decimal(str(invoice.get("outstanding_balance", 0)))
            if outstanding <= 0:
                continue

            # Check if overdue (with grace period)
            effective_due = due_date
            if grace_days > 0:
                from datetime import timedelta
                effective_due = due_date + timedelta(days=grace_days)

            if ctx.today <= effective_due:
                continue  # Not yet overdue

            findings.append(LeakageFinding(
                leakage_type=self.leakage_type,
                description=(
                    f"Invoice '{invoice.get('invoice_number', 'Unknown')}': "
                    f"due {due_date.isoformat()}, "
                    f"outstanding ${outstanding:.2f}"
                ),
                expected_amount=outstanding,
                actual_amount=Decimal("0"),
                potential_leakage=outstanding,
                customer_id=invoice.get("customer_id"),
                contract_id=invoice.get("contract_id"),
                invoice_id=invoice["id"],
            ))

        return findings
