"""Evaluation pipeline orchestrator.

Runs the complete detect → match → score pipeline against a seeded
synthetic dataset and produces measured precision/recall/FPR numbers.

Can be run as: python -m eval.run_evaluation
"""

from __future__ import annotations

import time
import uuid

from app.rules.base import RuleContext
from app.rules.engine import ALL_RULES
from eval.generate_dataset import GeneratedDataset, generate_dataset
from eval.ground_truth import build_ground_truth
from eval.metrics import (
    DetectedCase,
    EvaluationMetrics,
    compute_metrics,
    format_metrics_report,
)


def _run_rules_offline(
    dataset: GeneratedDataset,
    org_id: uuid.UUID,
    rules_to_run: list[str] | None = None,
) -> tuple[list[DetectedCase], list[float]]:
    """Run the rule engine against in-memory data (no database needed).

    Returns detected cases and per-case detection times in milliseconds.
    """
    detected: list[DetectedCase] = []
    detection_times: list[float] = []

    for rule in ALL_RULES:
        if rules_to_run and rule.leakage_type not in rules_to_run:
            continue

        ctx = RuleContext(
            organization_id=org_id,
            rule_version_id=uuid.uuid4(),
            parameters=rule.default_parameters,
            today=dataset.today,
            projects=dataset.projects,
            contracts=dataset.contracts,
            contract_lines=dataset.contract_lines,
            invoices=dataset.invoices,
            invoice_lines=dataset.invoice_lines,
            payments=dataset.payments,
            credit_notes=dataset.credit_notes,
        )

        start = time.perf_counter()
        findings = rule.evaluate(ctx)
        elapsed_ms = (time.perf_counter() - start) * 1000

        for finding in findings:
            detected.append(DetectedCase(
                leakage_type=finding.leakage_type,
                description=finding.description,
                potential_leakage=finding.potential_leakage,
                customer_id=finding.customer_id,
                contract_id=finding.contract_id,
                invoice_id=finding.invoice_id,
                project_id=finding.project_id,
                correlation_id=str(uuid.uuid4()),
                detection_time_ms=elapsed_ms / max(len(findings), 1),
            ))
            detection_times.append(elapsed_ms / max(len(findings), 1))

    return detected, detection_times


def run_evaluation(
    dataset: GeneratedDataset | None = None,
    rules_to_run: list[str] | None = None,
) -> EvaluationMetrics:
    """Run the complete evaluation pipeline.

    1. Generate (or use provided) dataset
    2. Build ground truth
    3. Run rules
    4. Compute metrics
    """
    from eval.generate_dataset import EVAL_ORG_ID

    if dataset is None:
        dataset = generate_dataset()

    ground_truth = build_ground_truth(dataset)
    detected, times = _run_rules_offline(dataset, EVAL_ORG_ID, rules_to_run)
    metrics = compute_metrics(detected, ground_truth, times)
    return metrics


def run_evaluation_with_disabled_rules(
    disabled_rules: list[str],
) -> EvaluationMetrics:
    """Run evaluation with specific rules disabled (for CI fail-case testing).

    Simulates a regression where certain detection rules are broken.
    """
    from eval.generate_dataset import EVAL_ORG_ID

    dataset = generate_dataset()
    ground_truth = build_ground_truth(dataset)

    all_rule_types = [r.leakage_type for r in ALL_RULES]
    active_rules = [r for r in all_rule_types if r not in disabled_rules]

    detected, times = _run_rules_offline(dataset, EVAL_ORG_ID, active_rules)
    metrics = compute_metrics(detected, ground_truth, times)
    return metrics


if __name__ == "__main__":
    print("Running RevenueGuard AI evaluation pipeline...")
    print()

    metrics = run_evaluation()
    print(format_metrics_report(metrics))

    # CI gate checks
    RECALL_FLOOR = 0.90
    FPR_CEILING = 0.05

    failed = False
    if metrics.recall < RECALL_FLOOR:
        print(f"FAIL: Recall {metrics.recall:.4f} below floor {RECALL_FLOOR}")
        failed = True
    if metrics.false_positive_rate > FPR_CEILING:
        print(f"FAIL: FPR {metrics.false_positive_rate:.4f} above ceiling {FPR_CEILING}")
        failed = True

    if failed:
        raise SystemExit(1)
    else:
        print("PASS: All CI gate checks passed.")
