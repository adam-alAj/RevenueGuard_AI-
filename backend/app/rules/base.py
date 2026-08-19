"""Base class and context for deterministic revenue leakage rules.

Every rule must:
- Be deterministic (no LLM involvement)
- Use Decimal for all monetary comparisons
- Read thresholds from RuleVersion.parameters (never hardcoded)
- Emit RevenueLeakageCase candidates with status="detected"
- Link to the specific RuleVersion that produced it
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class RuleContext:
    """Data needed by all rules — queried once, shared across all rule evaluations.

    This is populated by the engine from the database, so each rule
    doesn't need its own queries. All monetary values are Decimal.
    """

    organization_id: uuid.UUID
    rule_version_id: uuid.UUID
    parameters: dict[str, Any]
    today: date

    # Pre-queried data (populated by the engine)
    projects: list[dict[str, Any]] = field(default_factory=list)
    contracts: list[dict[str, Any]] = field(default_factory=list)
    contract_lines: list[dict[str, Any]] = field(default_factory=list)
    invoices: list[dict[str, Any]] = field(default_factory=list)
    invoice_lines: list[dict[str, Any]] = field(default_factory=list)
    payments: list[dict[str, Any]] = field(default_factory=list)
    credit_notes: list[dict[str, Any]] = field(default_factory=list)

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter value from the rule version configuration."""
        return self.parameters.get(key, default)

    def get_decimal_param(self, key: str, default: Decimal = Decimal("0")) -> Decimal:
        """Get a parameter value as Decimal."""
        val = self.parameters.get(key, default)
        return Decimal(str(val))


@dataclass
class LeakageFinding:
    """A single leakage finding emitted by a rule.

    The engine collects these and persists them as RevenueLeakageCase records.
    """

    leakage_type: str
    description: str
    expected_amount: Decimal
    actual_amount: Decimal
    potential_leakage: Decimal
    customer_id: uuid.UUID | None = None
    contract_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    severity: str | None = None


class BaseRule(ABC):
    """Abstract base class for all leakage detection rules."""

    @property
    @abstractmethod
    def leakage_type(self) -> str:
        """The LeakageType enum value for this rule."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable rule name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """What this rule detects."""

    @property
    @abstractmethod
    def default_parameters(self) -> dict[str, Any]:
        """Default threshold/configuration values."""

    @abstractmethod
    def evaluate(self, ctx: RuleContext) -> list[LeakageFinding]:
        """Evaluate the rule against the context data.

        Returns a list of findings (empty if nothing detected).
        Each finding must have exact dollar amounts — not "found something."
        """
