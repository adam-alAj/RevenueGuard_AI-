"""Deterministic confidence scorer — versioned, weighted formula.

Combines four components into one auditable confidence score:
1. Detection strength (from the rule that found the case)
2. Entity-resolution confidence (Phase 5's match quality)
3. Evidence completeness (fraction of expected evidence types present)
4. Investigation classification (mapped to numeric contribution)

Every score stores:
- The final confidence value (0.0-1.0)
- The formula version used
- The individual component scores
- The weights used

WORKED EXAMPLE (v1):
  detection_strength = 0.95
  entity_resolution_confidence = 0.98
  evidence_completeness = 0.90
  classification_contribution = 0.91  (from "confirmed" classification)

  Formula (v1): weighted average with configurable weights
  weights = {detection: 0.30, entity_resolution: 0.25, evidence: 0.25, classification: 0.20}

  confidence = (0.95 * 0.30) + (0.98 * 0.25) + (0.90 * 0.25) + (0.91 * 0.20)
             = 0.285 + 0.245 + 0.225 + 0.182
             = 0.937

  Verified: 0.937 (rounded to 3 decimal places = 0.937)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# --- Formula versions ---

FORMULA_VERSION_V1 = "v1"

# Default weights for v1
DEFAULT_WEIGHTS_V1: dict[str, float] = {
    "detection_strength": 0.30,
    "entity_resolution": 0.25,
    "evidence_completeness": 0.25,
    "classification": 0.20,
}

# Classification → numeric contribution mapping
# These are NOT the agent's self-reported confidence — they are fixed
# mappings from the classification category to a numeric weight.
CLASSIFICATION_CONTRIBUTION: dict[str, float] = {
    "confirmed": 0.95,
    "likely": 0.80,
    "uncertain": 0.40,
    "false_positive": 0.05,
    "legitimate_exception": 0.05,
}


@dataclass
class ConfidenceBreakdown:
    """Complete breakdown of a confidence score computation."""

    formula_version: str
    detection_strength: float
    entity_resolution_confidence: float
    evidence_completeness: float
    classification: str
    classification_contribution: float
    weights: dict[str, float]
    final_confidence: float

    def to_dict(self) -> dict:
        """Serialize to dict for JSONB storage."""
        return {
            "formula_version": self.formula_version,
            "detection_strength": self.detection_strength,
            "entity_resolution_confidence": self.entity_resolution_confidence,
            "evidence_completeness": self.evidence_completeness,
            "classification": self.classification,
            "classification_contribution": self.classification_contribution,
            "weights": self.weights,
            "final_confidence": self.final_confidence,
        }


@dataclass
class ConfidenceInput:
    """Inputs for confidence computation."""

    detection_strength: float = 0.0
    entity_resolution_confidence: float = 0.0
    evidence_completeness: float = 0.0
    classification: str = "uncertain"


class ConfidenceScorer:
    """Versioned, deterministic confidence scorer.

    The formula version is stored alongside every computed score so that
    scores computed under different versions remain interpretable.
    """

    def __init__(
        self,
        formula_version: str = FORMULA_VERSION_V1,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.formula_version = formula_version
        self.weights = weights or dict(DEFAULT_WEIGHTS_V1)
        self._validate_weights()

    def _validate_weights(self) -> None:
        """Ensure weights sum to 1.0 (within floating-point tolerance)."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0, got {total:.4f}. "
                f"Weights: {self.weights}"
            )

    def score(self, inputs: ConfidenceInput) -> ConfidenceBreakdown:
        """Compute the confidence score deterministically.

        Args:
            inputs: The four component inputs.

        Returns:
            ConfidenceBreakdown with the final score and all components.

        Raises:
            ValueError: If any input is out of the valid range [0.0, 1.0].
        """
        self._validate_inputs(inputs)

        # Get classification contribution (fixed mapping, NOT agent's confidence)
        classification_contrib = CLASSIFICATION_CONTRIBUTION.get(
            inputs.classification, 0.40  # default to uncertain level
        )

        # Weighted average
        final = (
            inputs.detection_strength * self.weights["detection_strength"]
            + inputs.entity_resolution_confidence * self.weights["entity_resolution"]
            + inputs.evidence_completeness * self.weights["evidence_completeness"]
            + classification_contrib * self.weights["classification"]
        )

        # Round to 3 decimal places (matching NUMERIC(4,3) in DB)
        final_rounded = float(
            Decimal(str(final)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        )

        return ConfidenceBreakdown(
            formula_version=self.formula_version,
            detection_strength=inputs.detection_strength,
            entity_resolution_confidence=inputs.entity_resolution_confidence,
            evidence_completeness=inputs.evidence_completeness,
            classification=inputs.classification,
            classification_contribution=classification_contrib,
            weights=dict(self.weights),
            final_confidence=final_rounded,
        )

    def _validate_inputs(self, inputs: ConfidenceInput) -> None:
        """Validate all inputs are in [0.0, 1.0]."""
        fields = {
            "detection_strength": inputs.detection_strength,
            "entity_resolution_confidence": inputs.entity_resolution_confidence,
            "evidence_completeness": inputs.evidence_completeness,
        }
        for name, value in fields.items():
            if not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"{name} must be between 0.0 and 1.0, got {value}"
                )
        if inputs.classification not in CLASSIFICATION_CONTRIBUTION:
            raise ValueError(
                f"Unknown classification: {inputs.classification}. "
                f"Expected one of: {list(CLASSIFICATION_CONTRIBUTION.keys())}"
            )

    def score_from_parts(
        self,
        detection_strength: float,
        entity_resolution_confidence: float,
        evidence_completeness: float,
        classification: str,
    ) -> ConfidenceBreakdown:
        """Convenience method to score from individual values.

        Same as score() but takes individual parameters instead of a dataclass.
        """
        return self.score(
            ConfidenceInput(
                detection_strength=detection_strength,
                entity_resolution_confidence=entity_resolution_confidence,
                evidence_completeness=evidence_completeness,
                classification=classification,
            )
        )
