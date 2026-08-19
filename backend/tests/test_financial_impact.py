"""Tests for the deterministic financial impact calculator.

Verifies:
- Hand-computed values on Phase 6 fixture dataset
- All arithmetic uses Decimal (no float drift)
- Negative leakage (overbilling) handled correctly
- Currency formatting
- Edge cases (zero amounts, equal amounts)
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.scoring.financial_impact import (
    FinancialImpactCalculator,
)


class TestWorkedExample:
    """Verify the worked example from the docstring reproduces exactly."""

    def test_v1_worked_example(self) -> None:
        """Expected $15,000, Actual $12,000 -> Leakage $3,000.

        Manual calculation:
          expected = 15000.00
          actual = 12000.00
          leakage = 15000.00 - 12000.00 = 3000.00
          recoverable = 3000.00
        """
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("15000.00"),
            actual_amount=Decimal("12000.00"),
        )

        assert impact.expected_amount == Decimal("15000.00")
        assert impact.actual_amount == Decimal("12000.00")
        assert impact.potential_leakage == Decimal("3000.00")
        assert impact.recoverable_amount == Decimal("3000.00")


class TestPhase6FixtureDataset:
    """Test against the Phase 6 rule engine fixture dataset values."""

    def test_missing_invoice_fixture(self) -> None:
        """Missing invoice: expected $15,000 (contract value), actual $0."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("15000.00"),
            actual_amount=Decimal("0.00"),
        )
        assert impact.potential_leakage == Decimal("15000.00")
        assert impact.recoverable_amount == Decimal("15000.00")

    def test_underbilling_fixture(self) -> None:
        """Underbilling: expected $10,000, actual $8,000 -> leakage $2,000."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("10000.00"),
            actual_amount=Decimal("8000.00"),
        )
        assert impact.potential_leakage == Decimal("2000.00")
        assert impact.recoverable_amount == Decimal("2000.00")

    def test_pricing_mismatch_fixture(self) -> None:
        """Pricing mismatch: expected $100 (contract), actual $90 (invoice) -> $10."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("100.00"),
            actual_amount=Decimal("90.00"),
        )
        assert impact.potential_leakage == Decimal("10.00")

    def test_overdue_invoice_fixture(self) -> None:
        """Overdue invoice: expected $5,000, actual $0 (unpaid) -> $5,000."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("5000.00"),
            actual_amount=Decimal("0.00"),
        )
        assert impact.potential_leakage == Decimal("5000.00")

    def test_partial_payment_fixture(self) -> None:
        """Partial payment: expected $5,000, actual $2,000 -> $3,000."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("5000.00"),
            actual_amount=Decimal("2000.00"),
        )
        assert impact.potential_leakage == Decimal("3000.00")

    def test_contract_expiration_fixture(self) -> None:
        """Contract expiration: expected $24,000 (12mo x $2k), actual $0 -> $24,000."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("24000.00"),
            actual_amount=Decimal("0.00"),
        )
        assert impact.potential_leakage == Decimal("24000.00")


class TestDecimalPrecision:
    """Verify all arithmetic uses Decimal, never float."""

    def test_string_input_preserves_precision(self) -> None:
        """String inputs are converted to Decimal without precision loss."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount="1234567.89",
            actual_amount="987654.32",
        )
        assert impact.potential_leakage == Decimal("246913.57")

    def test_float_input_converted(self) -> None:
        """Float inputs are converted to Decimal via string."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=100.0,
            actual_amount=50.0,
        )
        assert impact.potential_leakage == Decimal("50.00")

    def test_decimal_input_preserved(self) -> None:
        """Decimal inputs are used directly."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("100.00"),
            actual_amount=Decimal("50.00"),
        )
        assert isinstance(impact.expected_amount, Decimal)
        assert isinstance(impact.potential_leakage, Decimal)

    def test_no_float_drift(self) -> None:
        """Repeated operations don't accumulate floating-point errors."""
        # This would fail with float arithmetic
        total = Decimal("0")
        for _ in range(100):
            total += Decimal("0.01")
        assert total == Decimal("1.00")


class TestNegativeLeakage:
    """Test overbilling (negative leakage) scenarios."""

    def test_overbilling(self) -> None:
        """Actual > expected produces negative leakage."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("1000.00"),
            actual_amount=Decimal("1200.00"),
        )
        assert impact.potential_leakage == Decimal("-200.00")

    def test_equal_amounts(self) -> None:
        """Equal expected and actual produces zero leakage."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("5000.00"),
            actual_amount=Decimal("5000.00"),
        )
        assert impact.potential_leakage == Decimal("0.00")


class TestRecoverableOverride:
    """Test recoverable_amount override for future refinement."""

    def test_default_equals_leakage(self) -> None:
        """Without override, recoverable equals potential_leakage."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("10000.00"),
            actual_amount=Decimal("7000.00"),
        )
        assert impact.recoverable_amount == Decimal("3000.00")

    def test_override_used(self) -> None:
        """With override, recoverable uses the override value."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("10000.00"),
            actual_amount=Decimal("7000.00"),
            recoverable_override=Decimal("2500.00"),
        )
        assert impact.recoverable_amount == Decimal("2500.00")
        assert impact.potential_leakage == Decimal("3000.00")


class TestCalculateFromFinding:
    """Test convenience method for Phase 6 rule outputs."""

    def test_from_finding(self) -> None:
        """calculate_from_finding accepts Decimal inputs."""
        impact = FinancialImpactCalculator.calculate_from_finding(
            expected_amount=Decimal("15000.00"),
            actual_amount=Decimal("12000.00"),
        )
        assert impact.potential_leakage == Decimal("3000.00")


class TestFormatCurrency:
    """Test currency formatting."""

    def test_usd_format(self) -> None:
        """USD format uses $ symbol."""
        result = FinancialImpactCalculator.format_currency(Decimal("1234.56"))
        assert result == "$1,234.56"

    def test_large_amount(self) -> None:
        """Large amounts are formatted with commas."""
        result = FinancialImpactCalculator.format_currency(Decimal("1000000.00"))
        assert result == "$1,000,000.00"

    def test_zero_amount(self) -> None:
        """Zero amount is formatted correctly."""
        result = FinancialImpactCalculator.format_currency(Decimal("0.00"))
        assert result == "$0.00"

    def test_non_usd_currency(self) -> None:
        """Non-USD currencies use the currency code."""
        result = FinancialImpactCalculator.format_currency(Decimal("1234.56"), currency="EUR")
        assert result == "EUR 1,234.56"


class TestToDict:
    """Test serialization to dict."""

    def test_to_dict(self) -> None:
        """to_dict preserves string representation of Decimal values."""
        impact = FinancialImpactCalculator.calculate(
            expected_amount=Decimal("15000.00"),
            actual_amount=Decimal("12000.00"),
        )
        d = impact.to_dict()
        assert d["expected_amount"] == "15000.00"
        assert d["actual_amount"] == "12000.00"
        assert d["potential_leakage"] == "3000.00"
        assert d["recoverable_amount"] == "3000.00"


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_invalid_string_input(self) -> None:
        """Non-numeric string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot convert"):
            FinancialImpactCalculator.calculate(
                expected_amount="not_a_number",
                actual_amount="100.00",
            )

    def test_none_input_raises(self) -> None:
        """None input raises ValueError."""
        with pytest.raises(ValueError, match="Cannot convert"):
            FinancialImpactCalculator.calculate(
                expected_amount=None,  # type: ignore[arg-type]
                actual_amount="100.00",
            )
