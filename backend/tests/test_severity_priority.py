"""Tests for the deterministic severity and priority classifiers.

Verifies:
- Threshold boundary tests (exact boundary values)
- All severity levels producible
- All priority levels producible
- Age-based priority escalation
- Configurable thresholds
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.scoring.severity_priority import (
    PriorityClassifier,
    PriorityThresholds,
    SeverityClassifier,
    SeverityThresholds,
)


class TestSeverityBoundaries:
    """Threshold boundary tests for severity classification."""

    def test_critical_at_boundary(self) -> None:
        """$10,000 at 0.80 confidence -> critical."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("10000.00"),
            confidence=0.80,
        )
        assert result.severity == "critical"

    def test_critical_just_below_amount(self) -> None:
        """$9,999.99 at 0.80 confidence -> high (not critical)."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("9999.99"),
            confidence=0.80,
        )
        assert result.severity == "high"

    def test_critical_just_below_confidence(self) -> None:
        """$10,000 at 0.79 confidence -> high (not critical)."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("10000.00"),
            confidence=0.79,
        )
        assert result.severity == "high"

    def test_high_at_boundary(self) -> None:
        """$5,000 at any confidence -> high."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("5000.00"),
            confidence=0.50,
        )
        assert result.severity == "high"

    def test_high_just_below(self) -> None:
        """$4,999.99 at 0.89 confidence -> medium (not high)."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("4999.99"),
            confidence=0.89,
        )
        assert result.severity == "medium"

    def test_high_with_low_confidence_override(self) -> None:
        """$1,000+ at 0.90+ confidence -> high."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("1000.00"),
            confidence=0.90,
        )
        assert result.severity == "high"

    def test_medium_at_boundary(self) -> None:
        """$1,000 at 0.60 confidence -> medium."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("1000.00"),
            confidence=0.60,
        )
        assert result.severity == "medium"

    def test_medium_just_below(self) -> None:
        """$999.99 at 0.69 confidence -> low (not medium)."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("999.99"),
            confidence=0.69,
        )
        assert result.severity == "low"

    def test_medium_by_confidence(self) -> None:
        """$100 at 0.70 confidence -> medium (by confidence threshold)."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("100.00"),
            confidence=0.70,
        )
        assert result.severity == "medium"

    def test_low_default(self) -> None:
        """$100 at 0.50 confidence -> low."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("100.00"),
            confidence=0.50,
        )
        assert result.severity == "low"

    def test_low_zero_amount(self) -> None:
        """$0 at 0.30 confidence -> low."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("0.00"),
            confidence=0.30,
        )
        assert result.severity == "low"


class TestSeverityAge:
    """Tests for age-based severity considerations."""

    def test_age_calculated_correctly(self) -> None:
        """Age in days is calculated correctly."""
        classifier = SeverityClassifier()
        today = date(2026, 8, 19)
        detection = date(2026, 8, 12)
        result = classifier.classify(
            potential_leakage=Decimal("500.00"),
            confidence=0.50,
            detection_date=detection,
            today=today,
        )
        assert result.age_days == 7

    def test_no_date_defaults_to_zero(self) -> None:
        """No detection date defaults age to 0."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("500.00"),
            confidence=0.50,
        )
        assert result.age_days == 0


class TestSeverityCustomThresholds:
    """Tests for configurable severity thresholds."""

    def test_custom_thresholds(self) -> None:
        """Custom thresholds are used for classification."""
        custom = SeverityThresholds(
            critical_amount=Decimal("50000.00"),
            critical_confidence=0.95,
        )
        classifier = SeverityClassifier(thresholds=custom)

        # $10,000 is now NOT critical with custom thresholds
        result = classifier.classify(
            potential_leakage=Decimal("10000.00"),
            confidence=0.90,
        )
        assert result.severity != "critical"

        # $50,000 at 0.95 IS critical
        result = classifier.classify(
            potential_leakage=Decimal("50000.00"),
            confidence=0.95,
        )
        assert result.severity == "critical"


class TestSeverityAllLevels:
    """Verify all 4 severity levels are producible."""

    def test_critical_producible(self) -> None:
        """Critical is producible."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("10000.00"),
            confidence=0.80,
        )
        assert result.severity == "critical"

    def test_high_producible(self) -> None:
        """High is producible."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("5000.00"),
            confidence=0.50,
        )
        assert result.severity == "high"

    def test_medium_producible(self) -> None:
        """Medium is producible."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("1000.00"),
            confidence=0.50,
        )
        assert result.severity == "medium"

    def test_low_producible(self) -> None:
        """Low is producible."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("100.00"),
            confidence=0.50,
        )
        assert result.severity == "low"


class TestSeverityReason:
    """Tests for severity reason text."""

    def test_reason_includes_amount(self) -> None:
        """Reason includes the leakage amount."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("10000.00"),
            confidence=0.80,
        )
        assert "$10,000.00" in result.reason

    def test_reason_includes_confidence(self) -> None:
        """Reason includes the confidence score."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("10000.00"),
            confidence=0.80,
        )
        assert "80.0%" in result.reason


class TestPriorityBoundaries:
    """Threshold boundary tests for priority classification."""

    def test_p1_critical_young(self) -> None:
        """Critical severity, 3 days old -> P1."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="critical",
            detection_date=date(2026, 8, 16),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P1"

    def test_p1_boundary_exactly_7_days(self) -> None:
        """Critical severity, exactly 7 days old -> P1."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="critical",
            detection_date=date(2026, 8, 12),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P1"

    def test_p2_critical_aged(self) -> None:
        """Critical severity, 8 days old -> P2."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="critical",
            detection_date=date(2026, 8, 11),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P2"

    def test_p2_high_young(self) -> None:
        """High severity, 15 days old -> P2."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="high",
            detection_date=date(2026, 8, 4),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P2"

    def test_p2_boundary_exactly_30_days(self) -> None:
        """High severity, exactly 30 days old -> P2."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="high",
            detection_date=date(2026, 7, 20),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P2"

    def test_p3_high_aged(self) -> None:
        """High severity, 31 days old -> P3."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="high",
            detection_date=date(2026, 7, 19),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P3"

    def test_p3_medium(self) -> None:
        """Medium severity -> P3."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="medium",
            detection_date=date(2026, 8, 10),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P3"

    def test_p4_low(self) -> None:
        """Low severity -> P4."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="low",
            detection_date=date(2026, 8, 10),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P4"

    def test_p4_no_date(self) -> None:
        """Low severity with no date -> P4."""
        classifier = PriorityClassifier()
        result = classifier.classify(severity="low")
        assert result.priority == "P4"


class TestPriorityAllLevels:
    """Verify all 4 priority levels are producible."""

    def test_all_priorities_producible(self) -> None:
        """All P1-P4 are producible."""
        classifier = PriorityClassifier()
        today = date(2026, 8, 19)

        # P1: critical + young
        r1 = classifier.classify("critical", date(2026, 8, 16), today)
        assert r1.priority == "P1"

        # P2: high + young
        r2 = classifier.classify("high", date(2026, 8, 10), today)
        assert r2.priority == "P2"

        # P3: medium
        r3 = classifier.classify("medium", date(2026, 8, 10), today)
        assert r3.priority == "P3"

        # P4: low
        r4 = classifier.classify("low", date(2026, 8, 10), today)
        assert r4.priority == "P4"


class TestPriorityCustomThresholds:
    """Tests for configurable priority thresholds."""

    def test_custom_urgent_window(self) -> None:
        """Custom urgent window (3 days) changes P1 boundary."""
        custom = PriorityThresholds(urgent_max_age_days=3)
        classifier = PriorityClassifier(thresholds=custom)

        # 4 days old is now P2, not P1
        result = classifier.classify(
            severity="critical",
            detection_date=date(2026, 8, 15),
            today=date(2026, 8, 19),
        )
        assert result.priority == "P2"


class TestSerialization:
    """Tests for to_dict serialization."""

    def test_severity_to_dict(self) -> None:
        """SeverityResult serializes correctly."""
        classifier = SeverityClassifier()
        result = classifier.classify(
            potential_leakage=Decimal("10000.00"),
            confidence=0.80,
        )
        d = result.to_dict()
        assert d["severity"] == "critical"
        assert "reason" in d
        assert "potential_leakage" in d
        assert "confidence" in d
        assert "age_days" in d

    def test_priority_to_dict(self) -> None:
        """PriorityResult serializes correctly."""
        classifier = PriorityClassifier()
        result = classifier.classify(
            severity="critical",
            detection_date=date(2026, 8, 16),
            today=date(2026, 8, 19),
        )
        d = result.to_dict()
        assert d["priority"] == "P1"
        assert d["severity"] == "critical"
        assert d["age_days"] == 3
        assert "reason" in d
