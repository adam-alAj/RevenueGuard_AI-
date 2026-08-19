"""Missing Invoice rule.

Detects: Project.status == "completed" AND contract implies billing AND
no linked Invoice within the configured billing window.

Parameters:
- billing_window_days: days after project completion to expect an invoice (default: 30)
"""

from __future__ import annotations

from decimal import Decimal

from app.rules.base import BaseRule, LeakageFinding, RuleContext


class MissingInvoiceRule(BaseRule):
    leakage_type = "missing_invoice"
    name = "Missing Invoice"
    description = "Completed project with no invoice within the billing window"
    default_parameters = {"billing_window_days": 30}

    def evaluate(self, ctx: RuleContext) -> list[LeakageFinding]:
        findings = []
        window_days = ctx.get_param("billing_window_days", 30)

        for project in ctx.projects:
            if project["status"] != "completed":
                continue
            if not project.get("is_billable", True):
                continue

            project_id = project["id"]
            contract_id = project.get("contract_id")

            # Check if there's an invoice linked to this project
            has_invoice = any(
                inv["project_id"] == project_id
                for inv in ctx.invoices
            )
            if has_invoice:
                continue

            # Check billing window — if project ended recently, give it time
            end_date = project.get("end_date")
            if end_date and ctx.today:
                days_since = (ctx.today - end_date).days
                if days_since < window_days:
                    continue  # Still within the billing window

            # Find the contract to determine expected amount
            expected_amount = Decimal("0")
            if contract_id:
                for cl in ctx.contract_lines:
                    if cl["contract_id"] == contract_id:
                        expected_amount += Decimal(str(cl["quantity"])) * Decimal(str(cl["unit_price"]))

            findings.append(LeakageFinding(
                leakage_type=self.leakage_type,
                description=(
                    f"Project '{project.get('name', 'Unknown')}' is completed "
                    f"but has no linked invoice"
                ),
                expected_amount=expected_amount,
                actual_amount=Decimal("0"),
                potential_leakage=expected_amount,
                customer_id=project.get("customer_id"),
                contract_id=contract_id,
                project_id=project_id,
            ))

        return findings
