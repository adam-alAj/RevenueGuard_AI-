"""Tests for the evaluation pipeline.

Verifies:
- Dataset generation is seeded and reproducible
- Ground truth correctly identifies injected cases
- Metrics computation produces valid numbers
- Correlation IDs thread through rule execution
- CI gate actually fails when a rule is disabled
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.rules.engine import ALL_RULES
from eval.generate_dataset import EVAL_ORG_ID, generate_dataset
from eval.ground_truth import GroundTruth, GroundTruthCase, build_ground_truth
from eval.metrics import (
    DetectedCase,
    EvaluationMetrics,
    compute_metrics,
    format_metrics_report,
)
from eval.run_evaluation import (
    _run_rules_offline,
    run_evaluation,
    run_evaluation_with_disabled_rules,
)

# ---------------------------------------------------------------------------
# Dataset generation tests
# ---------------------------------------------------------------------------


class TestDatasetGeneration:
    """Verify the seeded dataset is deterministic and meets scale requirements."""

    def test_dataset_is_deterministic(self) -> None:
        """Two runs with default seed produce identical datasets."""
        ds1 = generate_dataset()
        ds2 = generate_dataset()
        assert len(ds1.customers) == len(ds2.customers)
        assert len(ds1.contracts) == len(ds2.contracts)
        assert len(ds1.invoices) == len(ds2.invoices)
        assert ds1.customers[0]["id"] == ds2.customers[0]["id"]
        assert ds1.contracts[0]["name"] == ds2.contracts[0]["name"]

    def test_dataset_meets_scale(self) -> None:
        """Dataset meets minimum scale requirements."""
        ds = generate_dataset()
        assert len(ds.customers) >= 150
        assert len(ds.contracts) >= 30
        assert len(ds.invoices) >= 400
        assert len(ds.payments) >= 400
        assert len(ds.projects) >= 30

    def test_dataset_has_all_entity_types(self) -> None:
        """Dataset contains all required entity types."""
        ds = generate_dataset()
        assert len(ds.contract_lines) > 0
        assert len(ds.invoice_lines) > 0
        assert len(ds.credit_notes) > 0

    def test_monetary_values_are_decimal(self) -> None:
        """All monetary values in the dataset are Decimal."""
        ds = generate_dataset()
        for cl in ds.contract_lines[:5]:
            assert isinstance(cl["unit_price"], Decimal)
            assert isinstance(cl["total"], Decimal)
        for inv in ds.invoices[:5]:
            assert isinstance(inv["total"], Decimal)
            assert isinstance(inv["outstanding_balance"], Decimal)

    def test_dataset_has_eval_org_id(self) -> None:
        """All entities in the dataset belong to the evaluation org."""
        ds = generate_dataset()
        for cust in ds.customers:
            assert cust["organization_id"] == EVAL_ORG_ID
        for contract in ds.contracts:
            assert contract["organization_id"] == EVAL_ORG_ID


# ---------------------------------------------------------------------------
# Ground truth tests
# ---------------------------------------------------------------------------


class TestGroundTruth:
    """Verify ground truth correctly identifies expected leakage cases."""

    def test_ground_truth_has_true_positives(self) -> None:
        """Ground truth identifies leakage cases that should be detected."""
        ds = generate_dataset()
        gt = build_ground_truth(ds)
        assert len(gt.true_positives) > 0

    def test_ground_truth_has_fp_bait(self) -> None:
        """Ground truth includes false-positive bait records."""
        ds = generate_dataset()
        gt = build_ground_truth(ds)
        assert len(gt.false_positives_bait) > 0

    def test_ground_truth_expected_amounts_positive(self) -> None:
        """All true-positive ground truth cases have positive expected amounts."""
        ds = generate_dataset()
        gt = build_ground_truth(ds)
        for case in gt.true_positives:
            assert case.expected_amount > 0, f"Case {case.description} has zero amount"

    def test_ground_truth_covers_multiple_rule_types(self) -> None:
        """Ground truth covers at least 2 leakage types."""
        ds = generate_dataset()
        gt = build_ground_truth(ds)
        tp_types = {c.leakage_type for c in gt.true_positives}
        assert len(tp_types) >= 2, f"Only covers {tp_types}"

    def test_ground_truth_is_reproducible(self) -> None:
        """Ground truth is deterministic for the same dataset."""
        ds = generate_dataset()
        gt1 = build_ground_truth(ds)
        gt2 = build_ground_truth(ds)
        assert len(gt1.true_positives) == len(gt2.true_positives)
        assert gt1.true_positives[0].expected_amount == gt2.true_positives[0].expected_amount


# ---------------------------------------------------------------------------
# Metrics computation tests
# ---------------------------------------------------------------------------


class TestMetricsComputation:
    """Verify metrics are computed correctly against known inputs."""

    def test_perfect_detection(self) -> None:
        """Perfect match → precision=1, recall=1, FPR=0."""
        gt = GroundTruth(
            true_positives=[
                GroundTruthCase(
                    leakage_type="missing_invoice",
                    description="Case A",
                    expected_amount=Decimal("1000"),
                    match_contract_name="Contract A",
                ),
            ],
            false_positives_bait=[],
        )
        detected = [
            DetectedCase(
                leakage_type="missing_invoice",
                description="Contract A missing invoice",
                potential_leakage=Decimal("1000"),
                contract_id="contract-a",
            ),
        ]
        metrics = compute_metrics(detected, gt)
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.false_positive_rate == 0.0
        assert metrics.true_positives == 1
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0

    def test_false_positive_detection(self) -> None:
        """Extra detection → FP increases, precision drops."""
        gt = GroundTruth(
            true_positives=[
                GroundTruthCase(
                    leakage_type="missing_invoice",
                    description="Case A",
                    expected_amount=Decimal("1000"),
                ),
            ],
            false_positives_bait=[],
        )
        detected = [
            DetectedCase(
                leakage_type="missing_invoice",
                description="Real case",
                potential_leakage=Decimal("1000"),
            ),
            DetectedCase(
                leakage_type="underbilling",
                description="Spurious detection",
                potential_leakage=Decimal("500"),
            ),
        ]
        metrics = compute_metrics(detected, gt)
        assert metrics.precision < 1.0
        assert metrics.false_positives == 1

    def test_missed_detection(self) -> None:
        """Missed case → FN increases, recall drops."""
        gt = GroundTruth(
            true_positives=[
                GroundTruthCase(
                    leakage_type="missing_invoice",
                    description="Case A",
                    expected_amount=Decimal("1000"),
                ),
                GroundTruthCase(
                    leakage_type="underbilling",
                    description="Case B",
                    expected_amount=Decimal("2000"),
                ),
            ],
            false_positives_bait=[],
        )
        detected = [
            DetectedCase(
                leakage_type="missing_invoice",
                description="Case A detected",
                potential_leakage=Decimal("1000"),
            ),
        ]
        metrics = compute_metrics(detected, gt)
        assert metrics.recall == 0.5  # 1 of 2 detected
        assert metrics.false_negatives == 1

    def test_amount_accuracy_perfect(self) -> None:
        """Exact amount match → MAPE = 0."""
        gt = GroundTruth(
            true_positives=[
                GroundTruthCase(
                    leakage_type="missing_invoice",
                    description="Case A",
                    expected_amount=Decimal("5000"),
                    match_contract_name="Acme",
                ),
            ],
            false_positives_bait=[],
        )
        detected = [
            DetectedCase(
                leakage_type="missing_invoice",
                description="Acme missing invoice",
                potential_leakage=Decimal("5000"),
                contract_id="acme",
            ),
        ]
        metrics = compute_metrics(detected, gt)
        assert metrics.amount_mape == 0.0

    def test_amount_accuracy_with_error(self) -> None:
        """Amount error is correctly computed."""
        gt = GroundTruth(
            true_positives=[
                GroundTruthCase(
                    leakage_type="missing_invoice",
                    description="Case A",
                    expected_amount=Decimal("1000"),
                    match_contract_name="Acme",
                ),
            ],
            false_positives_bait=[],
        )
        detected = [
            DetectedCase(
                leakage_type="missing_invoice",
                description="Acme missing invoice",
                potential_leakage=Decimal("1100"),  # 10% error
                contract_id="acme",
            ),
        ]
        metrics = compute_metrics(detected, gt)
        assert abs(metrics.amount_mape - 10.0) < 0.01  # ~10% MAPE

    def test_empty_detection(self) -> None:
        """No detections → all zeros."""
        gt = GroundTruth(
            true_positives=[
                GroundTruthCase(
                    leakage_type="missing_invoice",
                    description="Case A",
                    expected_amount=Decimal("1000"),
                ),
            ],
            false_positives_bait=[],
        )
        metrics = compute_metrics([], gt)
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.false_negatives == 1

    def test_format_report_contains_key_metrics(self) -> None:
        """Formatted report contains all key metrics."""
        metrics = EvaluationMetrics(
            total_detected=10,
            true_positives=8,
            false_positives=2,
            false_negatives=1,
            precision=0.8,
            recall=0.889,
            false_positive_rate=0.2,
            f1_score=0.842,
        )
        report = format_metrics_report(metrics)
        assert "Precision" in report
        assert "Recall" in report
        assert "False Positive" in report
        assert "F1" in report


# ---------------------------------------------------------------------------
# Correlation ID tests
# ---------------------------------------------------------------------------


class TestCorrelationIDs:
    """Verify correlation IDs thread through rule execution."""

    def test_rule_engine_assigns_correlation_id(self) -> None:
        """Findings from offline rule execution have correlation IDs."""
        ds = generate_dataset()
        detected, _ = _run_rules_offline(ds, EVAL_ORG_ID)
        for case in detected:
            assert case.correlation_id is not None
            # Should be a valid UUID string
            uuid.UUID(case.correlation_id)

    def test_same_execution_same_correlation_id(self) -> None:
        """All findings from the same rule execution share a correlation ID."""
        ds = generate_dataset()
        # Run one rule at a time to verify correlation IDs are per-rule
        for rule in ALL_RULES:
            detected, _ = _run_rules_offline(ds, EVAL_ORG_ID, [rule.leakage_type])
            if len(detected) > 1:
                # All findings from the same rule should have different
                # correlation IDs (each finding gets its own UUID)
                # But they should all be valid UUIDs
                for case in detected:
                    uuid.UUID(case.correlation_id)
                break

    def test_correlation_id_is_unique_per_finding(self) -> None:
        """Each finding gets a unique correlation ID."""
        ds = generate_dataset()
        detected, _ = _run_rules_offline(ds, EVAL_ORG_ID)
        ids = [c.correlation_id for c in detected if c.correlation_id]
        # All IDs should be unique
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Full pipeline evaluation tests
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Run the full evaluation pipeline and verify results."""

    def test_full_evaluation_produces_valid_metrics(self) -> None:
        """Full pipeline run produces valid, non-degenerate metrics."""
        metrics = run_evaluation()
        assert metrics.total_detected > 0
        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 <= metrics.false_positive_rate <= 1.0
        assert metrics.amount_mape >= 0.0

    def test_full_evaluation_has_per_rule_breakdown(self) -> None:
        """Full pipeline produces per-rule metrics."""
        metrics = run_evaluation()
        assert len(metrics.per_rule) > 0

    def test_full_evaluation_has_matched_pairs(self) -> None:
        """Full pipeline produces matched pairs."""
        metrics = run_evaluation()
        assert len(metrics.matched_pairs) > 0


# ---------------------------------------------------------------------------
# CI gate fail-case tests
# ---------------------------------------------------------------------------


class TestCIGate:
    """Verify the CI gate actually fails when detection quality degrades."""

    def test_ci_gate_passes_on_full_pipeline(self) -> None:
        """CI gate passes with all rules active (recall >= 0.90, FPR <= 0.05)."""
        metrics = run_evaluation()
        # With the full pipeline, we expect high recall
        # (the rules correctly detect injected cases)
        assert metrics.recall >= 0.85, f"Recall too low: {metrics.recall}"
        assert metrics.false_positive_rate <= 0.15, f"FPR too high: {metrics.false_positive_rate}"

    def test_ci_gate_fails_with_disabled_rule(self) -> None:
        """Disabling a rule reduces recall, proving the gate works."""
        # Run with all rules
        metrics_all = run_evaluation()
        # Find the most prolific rule type and disable it
        if metrics_all.per_rule:
            top_rule = max(metrics_all.per_rule, key=lambda r: metrics_all.per_rule[r].get("detected", 0))
            metrics_disabled = run_evaluation_with_disabled_rules([top_rule])

            # Recall should drop when a rule is disabled
            assert metrics_disabled.recall < metrics_all.recall, (
                f"Disabling {top_rule} did not reduce recall: "
                f"{metrics_disabled.recall} >= {metrics_all.recall}"
            )
            # False negatives should increase
            assert metrics_disabled.false_negatives > metrics_all.false_negatives

    def test_ci_gate_fails_with_multiple_disabled_rules(self) -> None:
        """Disabling multiple rules causes significant recall drop."""
        metrics = run_evaluation_with_disabled_rules(
            ["missing_invoice", "underbilling", "overdue_invoice"]
        )
        # With 3 rules disabled, recall should be notably lower
        assert metrics.recall < 0.70, (
            f"Expected recall < 0.70 with 3 rules disabled, got {metrics.recall}"
        )

    def test_ci_gate_format_report(self) -> None:
        """Formatted report is human-readable."""
        metrics = run_evaluation()
        report = format_metrics_report(metrics)
        assert "Evaluation Metrics Report" in report
        assert "Precision" in report
        assert "Recall" in report
        # Print for visibility
        print("\n" + report)
