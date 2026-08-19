"""Deterministic financial impact calculator — Decimal-backed.

All monetary calculations use Decimal, never float.
Every field on RevenueLeakageCase's financial-impact section is computed here:

- expected_amount: What should have been billed (from contract terms)
- actual_amount: What was actually billed/paid
- potential_leakage: expected_amount - actual_amount (may be negative for overbilling)
- recoverable_amount: MVP equals potential_leakage (field exists for future refinement)

WORKED EXAMPLE:
  expected_amount = Decimal("15000.00")  (contract value)
  actual_amount   = Decimal("12000.00")  (invoiced amount)

  potential_leakage = 15000.00 - 12000.00 = 3000.00
  recoverable_amount = 3000.00  (MVP: equals potential_leakage)

  Verified: expected=15000.00, actual=12000.00, leakage=3000.00, recoverable=3000.00
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class FinancialImpact:
    """Computed financial impact for a leakage case.

    All values are Decimal for precision — never float.
    """

    expected_amount: Decimal
    actual_amount: Decimal
    potential_leakage: Decimal
    recoverable_amount: Decimal

    def to_dict(self) -> dict[str, str]:
        """Serialize to dict for storage. Values are strings to preserve precision."""
        return {
            "expected_amount": str(self.expected_amount),
            "actual_amount": str(self.actual_amount),
            "potential_leakage": str(self.potential_leakage),
            "recoverable_amount": str(self.recoverable_amount),
        }


class FinancialImpactCalculator:
    """Deterministic financial impact calculator.

    All arithmetic uses Decimal. No rounding errors, no floating-point drift.
    """

    @staticmethod
    def calculate(
        expected_amount: Decimal | str | float,
        actual_amount: Decimal | str | float,
        recoverable_override: Decimal | str | float | None = None,
    ) -> FinancialImpact:
        """Calculate financial impact deterministically.

        Args:
            expected_amount: What should have been billed.
            actual_amount: What was actually billed/paid.
            recoverable_override: Override for recoverable_amount (for future use).
                If None, defaults to potential_leakage.

        Returns:
            FinancialImpact with all four fields computed.

        Raises:
            ValueError: If amounts cannot be converted to Decimal.
        """
        expected = _to_decimal(expected_amount, "expected_amount")
        actual = _to_decimal(actual_amount, "actual_amount")

        # Core calculation: potential_leakage = expected - actual
        potential_leakage = expected - actual

        # MVP: recoverable equals potential_leakage
        if recoverable_override is not None:
            recoverable = _to_decimal(recoverable_override, "recoverable_override")
        else:
            recoverable = potential_leakage

        return FinancialImpact(
            expected_amount=expected,
            actual_amount=actual,
            potential_leakage=potential_leakage,
            recoverable_amount=recoverable,
        )

    @staticmethod
    def calculate_from_finding(
        expected_amount: Decimal,
        actual_amount: Decimal,
    ) -> FinancialImpact:
        """Calculate from a LeakageFinding's amounts (already Decimal).

        Convenience method when working with Phase 6 rule outputs.
        """
        return FinancialImpactCalculator.calculate(
            expected_amount=expected_amount,
            actual_amount=actual_amount,
        )

    @staticmethod
    def format_currency(amount: Decimal, currency: str = "USD") -> str:
        """Format a Decimal amount as a human-readable currency string.

        Args:
            amount: The amount to format.
            currency: ISO 4217 currency code.

        Returns:
            Formatted string like "$1,234.56".
        """
        symbol = "$" if currency == "USD" else f"{currency} "
        formatted = f"{symbol}{amount:,.2f}"
        return formatted


def _to_decimal(value: Decimal | str | float, field_name: str) -> Decimal:
    """Convert a value to Decimal, raising a clear error on failure."""
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except Exception as e:
        raise ValueError(f"Cannot convert {field_name}={value!r} to Decimal: {e}") from e
