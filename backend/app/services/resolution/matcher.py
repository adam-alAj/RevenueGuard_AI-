"""Deterministic entity matcher with similarity scoring.

Matching priority:
1. Exact external_id match → always wins (similarity = 1.0)
2. Fuzzy match on canonicalized name → similarity score
3. No match → not linked

Similarity bands:
- High (≥ 0.85): auto-link, no human review needed
- Mid (0.50 - 0.84): queue for human review
- Low (< 0.50): do not link

All matching is deterministic — no LLM involvement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

# Similarity thresholds (configurable via RuleVersion in Phase 6)
HIGH_CONFIDENCE_THRESHOLD = 0.85
MID_CONFIDENCE_THRESHOLD = 0.50


@dataclass
class MatchCandidate:
    """A potential match between two entities."""

    source_entity_id: uuid.UUID
    match_entity_id: uuid.UUID
    similarity_score: float
    match_method: str  # "exact_id", "fuzzy_name", "fuzzy_email", etc.
    comparison_details: dict[str, Any] | None = None


def compare_exact_id(
    source_external_id: str | None,
    match_external_id: str | None,
) -> float:
    """Compare external IDs — exact match returns 1.0, else 0.0."""
    if not source_external_id or not match_external_id:
        return 0.0
    if source_external_id.strip() == match_external_id.strip():
        return 1.0
    return 0.0


def compare_names(source_name: str, match_name: str) -> float:
    """Compare canonicalized names using token-sort-ratio.

    Returns 0.0 to 1.0 similarity score.
    """
    if not source_name or not match_name:
        return 0.0
    return fuzz.token_sort_ratio(source_name, match_name) / 100.0


def compare_emails(source_email: str, match_email: str) -> float:
    """Compare canonicalized emails — exact match or high similarity."""
    if not source_email or not match_email:
        return 0.0
    if source_email == match_email:
        return 1.0
    # Partial match (same domain)
    source_domain = source_email.split("@")[-1] if "@" in source_email else ""
    match_domain = match_email.split("@")[-1] if "@" in match_email else ""
    if source_domain == match_domain and source_domain:
        return 0.7  # Same domain but different local part
    return 0.0


def compare_phones(source_phone: str, match_phone: str) -> float:
    """Compare canonicalized phone numbers."""
    if not source_phone or not match_phone:
        return 0.0
    if source_phone == match_phone:
        return 1.0
    # Partial match (last 7 digits)
    if len(source_phone) >= 7 and len(match_phone) >= 7 and source_phone[-7:] == match_phone[-7:]:
        return 0.8
    return 0.0


def compute_similarity(
    source_fields: dict[str, Any],
    match_fields: dict[str, Any],
) -> tuple[float, str, dict]:
    """Compute overall similarity between two entity field sets.

    Returns (score, method, details).
    """
    details = {}
    best_score = 0.0
    best_method = "none"

    # Check external_id first (highest priority)
    if "external_id" in source_fields and "external_id" in match_fields:
        score = compare_exact_id(source_fields["external_id"], match_fields["external_id"])
        details["external_id"] = score
        if score == 1.0:
            return 1.0, "exact_id", details

    # Check name similarity
    if "name" in source_fields and "name" in match_fields:
        score = compare_names(source_fields["name"], match_fields["name"])
        details["name"] = score
        if score > best_score:
            best_score = score
            best_method = "fuzzy_name"

    # Check email
    if "email" in source_fields and "email" in match_fields:
        score = compare_emails(source_fields["email"], match_fields["email"])
        details["email"] = score
        if score > best_score:
            best_score = score
            best_method = "fuzzy_email"

    # Check phone
    if "phone" in source_fields and "phone" in match_fields:
        score = compare_phones(source_fields["phone"], match_fields["phone"])
        details["phone"] = score
        if score > best_score:
            best_score = score
            best_method = "fuzzy_phone"

    return best_score, best_method, details


def classify_match(score: float) -> str:
    """Classify a similarity score into a band.

    Returns: "high", "mid", or "low".
    """
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if score >= MID_CONFIDENCE_THRESHOLD:
        return "mid"
    return "low"


def find_matches_for_entity(
    source_id: uuid.UUID,
    source_fields: dict[str, Any],
    existing_entities: list[dict[str, Any]],
    exclude_ids: set[uuid.UUID] | None = None,
) -> list[MatchCandidate]:
    """Find all potential matches for a source entity against existing entities.

    Args:
        source_id: The ID of the entity being matched
        source_fields: Canonical field values for the source entity
        existing_entities: List of dicts with 'id' and field values
        exclude_ids: IDs to exclude from matching (e.g., self)

    Returns:
        List of MatchCandidate sorted by similarity score (highest first)
    """
    exclude = exclude_ids or set()
    exclude.add(source_id)

    candidates = []
    for entity in existing_entities:
        entity_id = entity.get("id")
        if entity_id in exclude:
            continue

        score, method, details = compute_similarity(source_fields, entity)
        if score > 0:
            candidates.append(
                MatchCandidate(
                    source_entity_id=source_id,
                    match_entity_id=entity_id,
                    similarity_score=score,
                    match_method=method,
                    comparison_details=details,
                )
            )

    # Sort by score descending
    candidates.sort(key=lambda c: c.similarity_score, reverse=True)
    return candidates
