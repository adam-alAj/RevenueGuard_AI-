"""Pricing Mismatch rule.

Detects: ContractLine.unit_price != InvoiceLine.unit_price for matched
line items (matched by description similarity within the same contract).

No configurable threshold — any difference is a mismatch.
"""

from __future__ import annotations

from decimal import Decimal

from app.rules.base import BaseRule, LeakageFinding, RuleContext


class PricingMismatchRule(BaseRule):
    leakage_type = "pricing_mismatch"
    name = "Pricing Mismatch"
    description = "Invoice line price differs from contract line price"
    default_parameters = {}

    def evaluate(self, ctx: RuleContext) -> list[LeakageFinding]:
        findings: list[LeakageFinding] = []

        # Index contract lines by contract_id
        contract_lines_by_contract: dict[str, list] = {}
        for cl in ctx.contract_lines:
            cid = str(cl["contract_id"])
            contract_lines_by_contract.setdefault(cid, []).append(cl)

        # Index invoice lines by contract_id (via invoice)
        invoice_by_id = {str(inv["id"]): inv for inv in ctx.invoices}
        invoice_lines_by_contract: dict[str, list] = {}
        for il in ctx.invoice_lines:
            inv = invoice_by_id.get(str(il["invoice_id"]))
            if inv and inv.get("contract_id"):
                cid = str(inv["contract_id"])
                invoice_lines_by_contract.setdefault(cid, []).append(il)

        # Compare line items by description match within each contract
        for contract in ctx.contracts:
            cid = str(contract["id"])
            c_lines = contract_lines_by_contract.get(cid, [])
            i_lines = invoice_lines_by_contract.get(cid, [])

            for il in i_lines:
                il_desc = il.get("description", "").strip().lower()
                il_price = Decimal(str(il["unit_price"]))

                for cl in c_lines:
                    cl_desc = cl.get("description", "").strip().lower()
                    cl_price = Decimal(str(cl["unit_price"]))

                    # Match by description (exact or close)
                    if il_desc and cl_desc and il_desc == cl_desc and il_price != cl_price:
                        difference = cl_price - il_price
                        findings.append(LeakageFinding(
                            leakage_type=self.leakage_type,
                            description=(
                                f"Line '{il.get('description', 'Unknown')}': "
                                f"contract price ${cl_price:.2f} != "
                                f"invoice price ${il_price:.2f}"
                            ),
                            expected_amount=cl_price,
                            actual_amount=il_price,
                            potential_leakage=abs(difference),
                            customer_id=contract.get("customer_id"),
                            contract_id=contract["id"],
                            invoice_id=il.get("invoice_id"),
                        ))

        return findings
