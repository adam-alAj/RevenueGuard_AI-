"""Contract Expiration Leakage rule.

Detects: Contract.expiration_date < service date AND service is billable
AND no renewal contract exists.

Parameters:
- None (the logic is purely date-based)
"""

from __future__ import annotations

from decimal import Decimal

from app.rules.base import BaseRule, LeakageFinding, RuleContext


class ContractExpirationRule(BaseRule):
    leakage_type = "contract_expiration"
    name = "Contract Expiration Leakage"
    description = "Billable service delivered after contract expiration with no renewal"
    default_parameters = {}

    def evaluate(self, ctx: RuleContext) -> list[LeakageFinding]:
        findings = []

        # Build set of contract_ids that have renewal contracts
        # (contracts starting after another contract's expiration)
        contract_renewals: dict[str, bool] = {}
        for contract in ctx.contracts:
            parent_id = contract.get("parent_contract_id")
            if parent_id:
                contract_renewals[str(parent_id)] = True

        # Check projects for services delivered after contract expiration
        for project in ctx.projects:
            if not project.get("is_billable", True):
                continue

            contract_id = project.get("contract_id")
            if not contract_id:
                continue

            # Find the contract
            contract = None
            for c in ctx.contracts:
                if str(c["id"]) == str(contract_id):
                    contract = c
                    break

            if not contract:
                continue

            expiration_date = contract.get("expiration_date")
            if not expiration_date:
                continue

            # Check if there's a renewal
            if contract_renewals.get(str(contract_id)):
                continue  # Renewed — not a leak

            # Check if project ended after contract expiration
            end_date = project.get("end_date") or ctx.today
            if end_date <= expiration_date:
                continue  # Project ended before or on expiration — OK

            # Calculate expected amount from contract lines
            expected_amount = Decimal("0")
            for cl in ctx.contract_lines:
                if str(cl["contract_id"]) == str(contract_id):
                    expected_amount += Decimal(str(cl["quantity"])) * Decimal(str(cl["unit_price"]))

            # Check if there's an invoice for this project
            has_invoice = any(
                str(inv.get("project_id")) == str(project["id"])
                for inv in ctx.invoices
            )
            actual_amount = Decimal("0") if not has_invoice else expected_amount

            findings.append(LeakageFinding(
                leakage_type=self.leakage_type,
                description=(
                    f"Project '{project.get('name', 'Unknown')}': "
                    f"service delivered after contract '{contract.get('name', 'Unknown')}' "
                    f"expired on {expiration_date.isoformat()}, no renewal found"
                ),
                expected_amount=expected_amount,
                actual_amount=actual_amount,
                potential_leakage=expected_amount - actual_amount,
                customer_id=project.get("customer_id"),
                contract_id=contract_id,
                project_id=project["id"],
            ))

        return findings
