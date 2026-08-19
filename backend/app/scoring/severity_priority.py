"""Deterministic severity and priority classifiers — threshold-table driven.

Severity is computed from:
  - Financial impact (potential_leakage magnitude)
  - Confidence score
  - Age of the case (days since detection)

Priority is computed from:
  - Severity
  - Urgency of the recommended action
  - Whether the case has been assigned

All thresholds are configurable — changing a threshold must never require
a code deploy.

SEVERITY THRESHOLDS (v1):
  critical: potential_leakage >= $10,000 AND confidence >= 0.8
  high:     potential_leakage >= $5,000 OR (potential_leakage >= $1,000 AND confidence >= 0.9)
  medium:   potential_leakage >= $1,000 OR confidence >= 0.7
  low:      everything else

PRIORITY THRESHOLDS (v1):
  P1 (urgent):  severity == critical AND age <= 7 days
  P2 (high):    severity in (critical, high) AND age <= 30 days
  P3 (normal):  severity in (medium, high)
  P4 (low):     everything else
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class SeverityThresholds:
    """Configurable thresholds for severity classification.

    All monetary thresholds are Decimal for precision.
    """

    critical_amount: Decimal = Decimal("10000.00")
    critical_confidence: float = 0.80
    high_amount: Decimal = Decimal("5000.00")
    high_amount_low_confidence: Decimal = Decimal("1000.00")
    high_confidence_threshold: float = 0.90
    medium_amount: Decimal = Decimal("1000.00")
    medium_confidence: float = 0.70


@dataclass
class PriorityThresholds:
    """Configurable thresholds for priority classification."""

    urgent_max_age_days: int = 7
    high_max_age_days: int = 30


@dataclass
class SeverityResult:
    """Result of severity classification."""

    severity: str
    reason: str
    potential_leakage: Decimal
    confidence: float
    age_days: int

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "severity": self.severity,
            "reason": self.reason,
            "potential_leakage": str(self.potential_leakage),
            "confidence": self.confidence,
            "age_days": self.age_days,
        }


@dataclass
class PriorityResult:
    """Result of priority classification."""

    priority: str
    severity: str
    age_days: int
    reason: str

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "priority": self.priority,
            "severity": self.severity,
            "age_days": self.age_days,
            "reason": self.reason,
        }


class SeverityClassifier:
    """Deterministic severity classifier using configurable threshold tables."""

    def __init__(self, thresholds: SeverityThresholds | None = None) -> None:
        self.thresholds = thresholds or SeverityThresholds()

    def classify(
        self,
        potential_leakage: Decimal | str | float,
        confidence: float,
        detection_date: date | None = None,
        today: date | None = None,
    ) -> SeverityResult:
        """Classify severity deterministically.

        Args:
            potential_leakage: The potential leakage amount.
            confidence: The confidence score (0.0-1.0).
            detection_date: When the case was detected (for age calculation).
            today: Current date (for age calculation). Defaults to date.today().

        Returns:
            SeverityResult with severity level and reasoning.
        """
        if isinstance(potential_leakage, str):
            potential_leakage = Decimal(potential_leakage)
        elif isinstance(potential_leakage, float):
            potential_leakage = Decimal(str(potential_leakage))

        # Calculate age in days
        if detection_date and today:
            age_days = (today - detection_date).days
        elif detection_date:
            age_days = (date.today() - detection_date).days
        else:
            age_days = 0

        t = self.thresholds

        # Critical: high amount AND high confidence
        if (
            potential_leakage >= t.critical_amount
            and confidence >= t.critical_confidence
        ):
            return SeverityResult(
                severity="critical",
                reason=(
                    f"Critical: ${potential_leakage:,.2f} leakage with "
                    f"{confidence:.1%} confidence exceeds ${t.critical_amount:,.2f} "
                    f"threshold at {t.critical_confidence:.0%} confidence"
                ),
                potential_leakage=potential_leakage,
                confidence=confidence,
                age_days=age_days,
            )

        # High: large amount OR medium amount with high confidence
        if potential_leakage >= t.high_amount:
            return SeverityResult(
                severity="high",
                reason=(
                    f"High: ${potential_leakage:,.2f} leakage exceeds "
                    f"${t.high_amount:,.2f} threshold"
                ),
                potential_leakage=potential_leakage,
                confidence=confidence,
                age_days=age_days,
            )
        if (
            potential_leakage >= t.high_amount_low_confidence
            and confidence >= t.high_confidence_threshold
        ):
            return SeverityResult(
                severity="high",
                reason=(
                    f"High: ${potential_leakage:,.2f} leakage with "
                    f"{confidence:.1%} confidence (above {t.high_confidence_threshold:.0%} "
                    f"threshold for ${t.high_amount_low_confidence:,.2f}+ amounts)"
                ),
                potential_leakage=potential_leakage,
                confidence=confidence,
                age_days=age_days,
            )

        # Medium: moderate amount OR decent confidence
        if potential_leakage >= t.medium_amount:
            return SeverityResult(
                severity="medium",
                reason=(
                    f"Medium: ${potential_leakage:,.2f} leakage exceeds "
                    f"${t.medium_amount:,.2f} threshold"
                ),
                potential_leakage=potential_leakage,
                confidence=confidence,
                age_days=age_days,
            )
        if confidence >= t.medium_confidence:
            return SeverityResult(
                severity="medium",
                reason=(
                    f"Medium: {confidence:.1%} confidence exceeds "
                    f"{t.medium_confidence:.0%} threshold"
                ),
                potential_leakage=potential_leakage,
                confidence=confidence,
                age_days=age_days,
            )

        # Low: everything else
        return SeverityResult(
            severity="low",
            reason=(
                f"Low: ${potential_leakage:,.2f} leakage with "
                f"{confidence:.1%} confidence below all higher thresholds"
            ),
            potential_leakage=potential_leakage,
            confidence=confidence,
            age_days=age_days,
        )


class PriorityClassifier:
    """Deterministic priority classifier using severity + age thresholds."""

    def __init__(self, thresholds: PriorityThresholds | None = None) -> None:
        self.thresholds = thresholds or PriorityThresholds()

    def classify(
        self,
        severity: str,
        detection_date: date | None = None,
        today: date | None = None,
        assigned_to: str | None = None,
    ) -> PriorityResult:
        """Classify priority deterministically.

        Args:
            severity: The severity level (critical/high/medium/low).
            detection_date: When the case was detected.
            today: Current date.
            assigned_to: Whether the case has an assignee.

        Returns:
            PriorityResult with priority level and reasoning.
        """
        if detection_date and today:
            age_days = (today - detection_date).days
        elif detection_date:
            age_days = (date.today() - detection_date).days
        else:
            age_days = 0

        t = self.thresholds

        # P1 (urgent): critical severity and young
        if severity == "critical" and age_days <= t.urgent_max_age_days:
            return PriorityResult(
                priority="P1",
                severity=severity,
                age_days=age_days,
                reason=(
                    f"P1 urgent: critical severity case is {age_days} days old "
                    f"(within {t.urgent_max_age_days}-day window)"
                ),
            )

        # P2 (high): critical or high severity and not too old
        if severity in ("critical", "high") and age_days <= t.high_max_age_days:
            return PriorityResult(
                priority="P2",
                severity=severity,
                age_days=age_days,
                reason=(
                    f"P2 high: {severity} severity case is {age_days} days old "
                    f"(within {t.high_max_age_days}-day window)"
                ),
            )

        # P3 (normal): medium or high severity
        if severity in ("medium", "high"):
            return PriorityResult(
                priority="P3",
                severity=severity,
                age_days=age_days,
                reason=f"P3 normal: {severity} severity case",
            )

        # P4 (low): everything else
        return PriorityResult(
            priority="P4",
            severity=severity,
            age_days=age_days,
            reason=f"P4 low: {severity} severity case",
        )
