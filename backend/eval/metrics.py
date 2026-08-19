"""Evaluation metrics pipeline.

Computes precision, recall, false-positive rate, amount accuracy (MAPE),
and time-to-detection against known ground truth labels.

All metrics are computed deterministically — no LLM involvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from eval.ground_truth import GroundTruth, GroundTruthCase


@dataclass
class DetectedCase:
    """A case detected by the pipeline (output of rule engine)."""

    leakage_type: str
    description: str
    potential_leakage: Decimal
    customer_id: Any = None
    contract_id: Any = None
    invoice_id: Any = Any
    project_id: Any = None
    correlation_id: str | None = None
    detection_time_ms: float = 0.0


@dataclass
class EvaluationMetrics:
    """Complete evaluation metrics report."""

    # Counts
    total_detected: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    # Rates
    precision: float = 0.0
    recall: float = 0.0
    false_positive_rate: float = 0.0
    f1_score: float = 0.0

    # Amount accuracy
    amount_mape: float = 0.0  # Mean Absolute Percentage Error
    amount_rmse: float = 0.0  # Root Mean Squared Error

    # Timing
    avg_detection_time_ms: float = 0.0
    p95_detection_time_ms: float = 0.0

    # Per-rule breakdown
    per_rule: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Matched and unmatched details
    matched_pairs: list[dict[str, Any]] = field(default_factory=list)
    unmatched_detected: list[str] = field(default_factory=list)
    unmatched_ground_truth: list[str] = field(default_factory=list)


def _match_detected_to_ground_truth(
    detected: list[DetectedCase],
    ground_truth: GroundTruth,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Match detected cases to ground truth using entity name matching.

    Returns (matched_pairs, unmatched_detected, unmatched_gt_descriptions).
    """
    matched_pairs: list[dict[str, Any]] = []
    used_gt: set[int] = set()

    for det in detected:
        best_match: GroundTruthCase | None = None
        best_idx = -1

        for idx, gt in enumerate(ground_truth.true_positives):
            if idx in used_gt:
                continue
            if gt.leakage_type != det.leakage_type:
                continue

            # Match by contract name (in description text)
            if gt.match_contract_name and gt.match_contract_name in det.description:
                best_match = gt
                best_idx = idx
                break

            # Match by invoice number (in description text)
            if gt.match_invoice_number and gt.match_invoice_number in det.description:
                best_match = gt
                best_idx = idx
                break

            # Match by project name (in description text)
            if gt.match_project_name and gt.match_project_name in det.description:
                best_match = gt
                best_idx = idx
                break

            # Fallback: match by leakage type + amount proximity
            if gt.leakage_type == det.leakage_type and best_match is None:
                best_match = gt
                best_idx = idx

        if best_match is not None:
            used_gt.add(best_idx)
            matched_pairs.append({
                "detected": det,
                "ground_truth": best_match,
                "amount_error": abs(float(det.potential_leakage - best_match.expected_amount)),
                "amount_error_pct": (
                    abs(float(det.potential_leakage - best_match.expected_amount))
                    / float(best_match.expected_amount)
                    * 100
                    if best_match.expected_amount > 0
                    else 0.0
                ),
            })

    unmatched_gt = [
        gt.description
        for idx, gt in enumerate(ground_truth.true_positives)
        if idx not in used_gt
    ]

    unmatched_det = [
        det.description
        for det in detected
        if not any(m["detected"] is det for m in matched_pairs)
    ]

    return matched_pairs, unmatched_det, unmatched_gt


def compute_metrics(
    detected: list[DetectedCase],
    ground_truth: GroundTruth,
    detection_times_ms: list[float] | None = None,
) -> EvaluationMetrics:
    """Compute all evaluation metrics.

    Args:
        detected: Cases detected by the pipeline.
        ground_truth: Known ground truth labels.
        detection_times_ms: Per-case detection latency in milliseconds.

    Returns:
        EvaluationMetrics with all computed metrics.
    """
    matched, unmatched_det, unmatched_gt = _match_detected_to_ground_truth(
        detected, ground_truth
    )

    tp = len(matched)
    fp = len(unmatched_det)
    fn = len(unmatched_gt)
    total_det = len(detected)

    # Precision / Recall / FPR
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fp_rate = fp / (fp + tp) if (fp + tp) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Amount accuracy (MAPE)
    amount_errors = [m["amount_error_pct"] for m in matched]
    mape = sum(amount_errors) / len(amount_errors) if amount_errors else 0.0

    # RMSE
    squared_errors = [m["amount_error"] ** 2 for m in matched]
    rmse = (sum(squared_errors) / len(squared_errors)) ** 0.5 if squared_errors else 0.0

    # Timing
    avg_time = 0.0
    p95_time = 0.0
    if detection_times_ms:
        avg_time = sum(detection_times_ms) / len(detection_times_ms)
        sorted_times = sorted(detection_times_ms)
        p95_idx = int(len(sorted_times) * 0.95)
        p95_time = sorted_times[min(p95_idx, len(sorted_times) - 1)]

    # Per-rule breakdown
    per_rule: dict[str, dict[str, Any]] = {}
    for m in matched:
        rule_type = m["detected"].leakage_type
        if rule_type not in per_rule:
            per_rule[rule_type] = {
                "detected": 0, "matched": 0, "missed": 0,
                "total_amount_error_pct": 0.0,
            }
        per_rule[rule_type]["detected"] += 1
        per_rule[rule_type]["matched"] += 1
        per_rule[rule_type]["total_amount_error_pct"] += m["amount_error_pct"]

    for det in unmatched_det:
        # Find what type it is
        rule_type = det.leakage_type if hasattr(det, "leakage_type") else "unknown"
        if rule_type not in per_rule:
            per_rule[rule_type] = {
                "detected": 0, "matched": 0, "missed": 0,
                "total_amount_error_pct": 0.0,
            }
        per_rule[rule_type]["detected"] += 1
        per_rule[rule_type]["missed"] += 1

    # Average amount error per rule
    for _rule_type, stats in per_rule.items():
        if stats["matched"] > 0:
            stats["avg_amount_error_pct"] = (
                stats["total_amount_error_pct"] / stats["matched"]
            )
        else:
            stats["avg_amount_error_pct"] = 0.0
        del stats["total_amount_error_pct"]

    return EvaluationMetrics(
        total_detected=total_det,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        false_positive_rate=fp_rate,
        f1_score=f1,
        amount_mape=mape,
        amount_rmse=rmse,
        avg_detection_time_ms=avg_time,
        p95_detection_time_ms=p95_time,
        per_rule=per_rule,
        matched_pairs=[
            {
                "detected_type": m["detected"].leakage_type,
                "ground_truth_type": m["ground_truth"].leakage_type,
                "detected_amount": str(m["detected"].potential_leakage),
                "expected_amount": str(m["ground_truth"].expected_amount),
                "error_pct": round(m["amount_error_pct"], 2),
            }
            for m in matched
        ],
        unmatched_detected=unmatched_det,
        unmatched_ground_truth=unmatched_gt,
    )


def format_metrics_report(metrics: EvaluationMetrics) -> str:
    """Format metrics into a human-readable report."""
    lines = [
        "=" * 70,
        "  RevenueGuard AI — Evaluation Metrics Report",
        "=" * 70,
        "",
        f"  Total Detected:     {metrics.total_detected}",
        f"  True Positives:     {metrics.true_positives}",
        f"  False Positives:    {metrics.false_positives}",
        f"  False Negatives:    {metrics.false_negatives}",
        "",
        f"  Precision:          {metrics.precision:.4f} ({metrics.precision * 100:.1f}%)",
        f"  Recall:             {metrics.recall:.4f} ({metrics.recall * 100:.1f}%)",
        f"  False Positive Rate:{metrics.false_positive_rate:.4f} ({metrics.false_positive_rate * 100:.1f}%)",
        f"  F1 Score:           {metrics.f1_score:.4f}",
        "",
        f"  Amount MAPE:        {metrics.amount_mape:.2f}%",
        f"  Amount RMSE:        ${metrics.amount_rmse:,.2f}",
        "",
        f"  Avg Detection Time: {metrics.avg_detection_time_ms:.1f}ms",
        f"  P95 Detection Time: {metrics.p95_detection_time_ms:.1f}ms",
        "",
    ]

    if metrics.per_rule:
        lines.append("  Per-Rule Breakdown:")
        lines.append("  " + "-" * 60)
        for rule, stats in sorted(metrics.per_rule.items()):
            lines.append(
                f"  {rule:<25} detected={stats['detected']:>3}  "
                f"matched={stats['matched']:>3}  "
                f"missed={stats['missed']:>3}  "
                f"avg_err={stats.get('avg_amount_error_pct', 0):.1f}%"
            )
        lines.append("")

    if metrics.unmatched_ground_truth:
        lines.append(f"  Missed Cases ({len(metrics.unmatched_ground_truth)}):")
        for desc in metrics.unmatched_ground_truth[:5]:
            lines.append(f"    - {desc}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)
