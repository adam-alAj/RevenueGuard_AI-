"""Ground truth labels for injected leakage cases.

Defines which leakage cases SHOULD be detected by each rule, with their
exact expected amounts. This is the gold standard against which the
pipeline's output is measured.

Categories:
1. TRUE POSITIVE cases — must be detected (injected leakage)
2. FALSE POSITIVE bait — must NOT be detected (clean records with near-miss features)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from eval.generate_dataset import GeneratedDataset


@dataclass
class GroundTruthCase:
    """A single known-answer leakage case."""

    leakage_type: str
    description: str
    expected_amount: Decimal
    # Matching criteria (any of these can be used to link detected → ground truth)
    match_customer_name: str | None = None
    match_contract_name: str | None = None
    match_invoice_number: str | None = None
    match_project_name: str | None = None
    # Whether this should be detected
    should_detect: bool = True


@dataclass
class GroundTruth:
    """Complete ground truth for a generated dataset."""

    true_positives: list[GroundTruthCase]
    false_positives_bait: list[GroundTruthCase]
    evaluation_org_id: Any = None  # uuid.UUID

    @property
    def all_tp_cases(self) -> list[GroundTruthCase]:
        return self.true_positives

    @property
    def all_fp_bait(self) -> list[GroundTruthCase]:
        return self.false_positives_bait

    @property
    def total_expected_detections(self) -> int:
        return len(self.true_positives)

    @property
    def total_fp_bait_count(self) -> int:
        return len(self.false_positives_bait)


def build_ground_truth(dataset: GeneratedDataset) -> GroundTruth:
    """Analyze the generated dataset and determine expected leakage cases.

    By examining the seeded data's known properties, we can determine
    exactly which cases the rules SHOULD and SHOULD NOT detect.
    """
    from eval.generate_dataset import EVAL_ORG_ID

    true_positives: list[GroundTruthCase] = []
    false_positives_bait: list[GroundTruthCase] = []

    # ── Missing Invoice cases ────────────────────────────────────────────
    # Projects that are completed, billable, have a contract, and have no invoice
    invoiced_project_ids = {
        inv.get("project_id") for inv in dataset.invoices if inv.get("project_id")
    }
    for project in dataset.projects:
        if project["status"] != "completed":
            continue
        if not project.get("is_billable", True):
            continue
        pid = project["id"]
        if pid in invoiced_project_ids:
            continue

        # Find the contract and calculate expected amount
        contract_id = project.get("contract_id")
        expected = Decimal("0")
        for cl in dataset.contract_lines:
            if cl["contract_id"] == contract_id:
                expected += Decimal(str(cl["quantity"])) * Decimal(str(cl["unit_price"]))

        if expected > 0:
            true_positives.append(
                GroundTruthCase(
                    leakage_type="missing_invoice",
                    description=f"Missing invoice for project {project['name']}",
                    expected_amount=expected,
                    match_project_name=project["name"],
                    match_contract_name=next(
                        (c["name"] for c in dataset.contracts if c["id"] == contract_id),
                        None,
                    ),
                )
            )

    # ── Underbilling cases ──────────────────────────────────────────────
    # Contracts where invoiced amount is significantly less than contracted
    contract_expected: dict[str, Decimal] = {}
    for cl in dataset.contract_lines:
        cid = str(cl["contract_id"])
        amt = Decimal(str(cl["quantity"])) * Decimal(str(cl["unit_price"]))
        contract_expected[cid] = contract_expected.get(cid, Decimal("0")) + amt

    # Group invoice lines by contract
    invoice_by_id = {str(inv["id"]): inv for inv in dataset.invoices}
    contract_actual: dict[str, Decimal] = {}
    for il in dataset.invoice_lines:
        inv = invoice_by_id.get(str(il["invoice_id"]))
        if inv and inv.get("contract_id"):
            cid = str(inv["contract_id"])
            amt = Decimal(str(il["quantity"])) * Decimal(str(il["unit_price"]))
            contract_actual[cid] = contract_actual.get(cid, Decimal("0")) + amt

    for contract in dataset.contracts:
        cid = str(contract["id"])
        expected_val = contract_expected.get(cid, Decimal("0"))
        actual_val = contract_actual.get(cid, Decimal("0"))
        if expected_val == 0:
            continue
        diff = expected_val - actual_val
        if diff > Decimal("100") and diff / expected_val > Decimal("0.05"):
            true_positives.append(
                GroundTruthCase(
                    leakage_type="underbilling",
                    description=f"Underbilling for {contract['name']}: expected {expected_val}, got {actual_val}",
                    expected_amount=diff,
                    match_contract_name=contract["name"],
                )
            )

    # ── Overdue Invoice cases ───────────────────────────────────────────
    for inv in dataset.invoices:
        due = inv.get("due_date")
        outstanding = Decimal(str(inv.get("outstanding_balance", 0)))
        if outstanding <= 0 or due is None:
            continue
        if due < dataset.today:
            true_positives.append(
                GroundTruthCase(
                    leakage_type="overdue_invoice",
                    description=f"Overdue invoice {inv['invoice_number']}: outstanding {outstanding}",
                    expected_amount=outstanding,
                    match_invoice_number=inv["invoice_number"],
                )
            )

    # ── Partial Payment cases ───────────────────────────────────────────
    # Invoices with outstanding balance and no credit notes explaining the gap
    cn_by_inv: dict[str, list] = {}
    for cn in dataset.credit_notes:
        inv_id = str(cn.get("invoice_id", ""))
        cn_by_inv.setdefault(inv_id, []).append(cn)

    for inv in dataset.invoices:
        outstanding = Decimal(str(inv.get("outstanding_balance", 0)))
        if outstanding <= 0:
            continue
        inv_id = str(inv["id"])
        cn_total = sum(Decimal(str(cn["amount"])) for cn in cn_by_inv.get(inv_id, []))
        if cn_total < outstanding:
            gap = outstanding - cn_total
            true_positives.append(
                GroundTruthCase(
                    leakage_type="partial_payment",
                    description=f"Partial payment gap for {inv['invoice_number']}: {gap}",
                    expected_amount=gap,
                    match_invoice_number=inv["invoice_number"],
                )
            )

    # ── Contract Expiration cases ────────────────────────────────────────
    renewal_map: dict[str, bool] = {}
    for c in dataset.contracts:
        parent = c.get("parent_contract_id")
        if parent:
            renewal_map[str(parent)] = True

    for project in dataset.projects:
        if not project.get("is_billable", True):
            continue
        contract_id = project.get("contract_id")
        if not contract_id:
            continue
        contract = next(
            (c for c in dataset.contracts if c["id"] == contract_id),
            None,
        )
        if not contract:
            continue
        exp = contract.get("expiration_date")
        if not exp:
            continue
        if renewal_map.get(str(contract_id)):
            continue
        end = project.get("end_date") or dataset.today
        if end <= exp:
            continue

        expected = Decimal("0")
        for cl in dataset.contract_lines:
            if cl["contract_id"] == contract_id:
                expected += Decimal(str(cl["quantity"])) * Decimal(str(cl["unit_price"]))

        has_inv = any(inv.get("project_id") == project["id"] for inv in dataset.invoices)
        leakage = expected if not has_inv else expected - expected  # 0 if invoiced
        if leakage > 0:
            true_positives.append(
                GroundTruthCase(
                    leakage_type="contract_expiration",
                    description=f"Contract expired for {contract['name']}, service {project['name']}",
                    expected_amount=leakage,
                    match_project_name=project["name"],
                    match_contract_name=contract["name"],
                )
            )

    # ── False Positive Bait ─────────────────────────────────────────────
    # Clean records with near-miss features that should NOT trigger detections

    # 1. Contract with amendment (renewal exists) — should not flag
    for contract in dataset.contracts:
        cid = str(contract["id"])
        if renewal_map.get(cid):
            false_positives_bait.append(
                GroundTruthCase(
                    leakage_type="contract_expiration",
                    description=f"Contract {contract['name']} has renewal — should not flag",
                    expected_amount=Decimal("0"),
                    match_contract_name=contract["name"],
                    should_detect=False,
                )
            )

    # 2. Fully paid invoices — should not flag
    for inv in dataset.invoices:
        if Decimal(str(inv.get("outstanding_balance", 0))) <= 0:
            false_positives_bait.append(
                GroundTruthCase(
                    leakage_type="partial_payment",
                    description=f"Invoice {inv['invoice_number']} fully paid — should not flag",
                    expected_amount=Decimal("0"),
                    match_invoice_number=inv["invoice_number"],
                    should_detect=False,
                )
            )

    # 3. Active projects (not completed) — should not flag missing invoice
    for project in dataset.projects:
        if project["status"] != "completed":
            false_positives_bait.append(
                GroundTruthCase(
                    leakage_type="missing_invoice",
                    description=f"Active project {project['name']} — should not flag",
                    expected_amount=Decimal("0"),
                    match_project_name=project["name"],
                    should_detect=False,
                )
            )

    return GroundTruth(
        true_positives=true_positives,
        false_positives_bait=false_positives_bait,
        evaluation_org_id=EVAL_ORG_ID,
    )
