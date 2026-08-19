"""Tests for entity matching and resolution.

Key tests:
- The "Acme Inc." / "ACME INC" / "Acme Incorporated" / "ACME" example
  resolves to a single Customer record
- No auto-merge below high-confidence threshold
- Similarity bands: high → auto-link, mid → review queue, low → no link
- Exact external_id always wins over fuzzy matching
- Cross-tenant isolation for resolution candidates
"""

from __future__ import annotations

import uuid

from app.services.resolution.matcher import (
    HIGH_CONFIDENCE_THRESHOLD,
    MID_CONFIDENCE_THRESHOLD,
    MatchCandidate,
    classify_match,
    compare_emails,
    compare_exact_id,
    compare_names,
    compare_phones,
    find_matches_for_entity,
)
from app.services.resolution.normalizer import canonicalize_name
from app.services.resolution.review_queue import (
    confirm_match,
    create_candidates,
    get_pending_candidates,
    reject_match,
)

# ---------------------------------------------------------------------------
# Canonicalization + matching integration test (the Acme Inc. example)
# ---------------------------------------------------------------------------


class TestAcmeIncResolution:
    """The canonical example: 4 variations of 'Acme' must resolve to one record."""

    def test_all_variations_canonicalize_to_same(self) -> None:
        """All 4 Acme variations canonicalize to 'acme'."""
        variations = ["Acme Inc.", "ACME INC", "Acme Incorporated", "ACME"]
        canonical = {canonicalize_name(v) for v in variations}
        assert canonical == {"acme"}, f"Expected all to canonicalize to 'acme', got {canonical}"

    def test_acme_variations_all_match_each_other(self) -> None:
        """Every pair of Acme variations has high similarity."""
        variations = ["Acme Inc.", "ACME INC", "Acme Incorporated", "ACME"]
        canonical = [canonicalize_name(v) for v in variations]

        for i, c1 in enumerate(canonical):
            for j, c2 in enumerate(canonical):
                if i != j:
                    score = compare_names(c1, c2)
                    assert score >= HIGH_CONFIDENCE_THRESHOLD, (
                        f"'{variations[i]}' vs '{variations[j]}' "
                        f"scored {score:.3f}, expected ≥ {HIGH_CONFIDENCE_THRESHOLD}"
                    )

    def test_acme_matches_globex_low(self) -> None:
        """Acme and Globex should have low similarity."""
        score = compare_names(canonicalize_name("Acme Inc."), canonicalize_name("Globex Corp"))
        assert score < MID_CONFIDENCE_THRESHOLD

    def test_find_matches_acme_in_existing(self) -> None:
        """Finding matches for 'Acme Inc.' against existing records."""
        acme_id = uuid.uuid4()
        globex_id = uuid.uuid4()
        initech_id = uuid.uuid4()

        existing = [
            {"id": acme_id, "name": canonicalize_name("ACME INC")},
            {"id": globex_id, "name": canonicalize_name("Globex Corp")},
            {"id": initech_id, "name": canonicalize_name("Initech LLC")},
        ]

        source = {"name": canonicalize_name("Acme Incorporated")}
        matches = find_matches_for_entity(uuid.uuid4(), source, existing)

        # Should find Acme as the top match with high confidence
        assert len(matches) >= 1
        assert matches[0].match_entity_id == acme_id
        assert matches[0].similarity_score >= HIGH_CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Similarity band tests
# ---------------------------------------------------------------------------


class TestSimilarityBands:
    def test_high_band(self) -> None:
        assert classify_match(0.90) == "high"
        assert classify_match(0.85) == "high"
        assert classify_match(1.0) == "high"

    def test_mid_band(self) -> None:
        assert classify_match(0.70) == "mid"
        assert classify_match(0.50) == "mid"

    def test_low_band(self) -> None:
        assert classify_match(0.49) == "low"
        assert classify_match(0.0) == "low"

    def test_no_auto_merge_below_threshold(self) -> None:
        """A score below 0.85 must NOT be auto-linked."""
        band = classify_match(0.80)
        assert band != "high"
        assert band == "mid"


# ---------------------------------------------------------------------------
# Comparison function tests
# ---------------------------------------------------------------------------


class TestCompareExactId:
    def test_exact_match(self) -> None:
        assert compare_exact_id("C001", "C001") == 1.0

    def test_no_match(self) -> None:
        assert compare_exact_id("C001", "C002") == 0.0

    def test_none_values(self) -> None:
        assert compare_exact_id(None, "C001") == 0.0
        assert compare_exact_id("C001", None) == 0.0

    def test_whitespace_handling(self) -> None:
        assert compare_exact_id(" C001 ", "C001") == 1.0


class TestCompareNames:
    def test_identical(self) -> None:
        assert compare_names("acme", "acme") == 1.0

    def test_similar(self) -> None:
        score = compare_names("acme", "acme inc")
        # "acme" vs "acme inc" — token_sort_ratio gives ~0.67
        assert score >= 0.5

    def test_different(self) -> None:
        score = compare_names("acme", "globex")
        assert score < 0.5

    def test_empty(self) -> None:
        assert compare_names("", "acme") == 0.0


class TestCompareEmails:
    def test_exact(self) -> None:
        assert compare_emails("test@example.com", "test@example.com") == 1.0

    def test_same_domain(self) -> None:
        score = compare_emails("alice@acme.com", "bob@acme.com")
        assert score == 0.7

    def test_different_domain(self) -> None:
        assert compare_emails("test@acme.com", "test@globex.com") == 0.0


class TestComparePhones:
    def test_exact(self) -> None:
        assert compare_phones("5550101", "5550101") == 1.0

    def test_same_last_7(self) -> None:
        score = compare_phones("15550101", "5550101")
        assert score == 0.8

    def test_different(self) -> None:
        assert compare_phones("5550101", "9990999") == 0.0


# ---------------------------------------------------------------------------
# Review queue tests (require DB session)
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.asyncio
async def test_create_candidates_high_auto_links(db_session) -> None:
    """High-confidence matches are auto-linked, not queued."""
    org_id = uuid.uuid4()
    source_id = uuid.uuid4()
    match_id = uuid.uuid4()

    candidates = [
        MatchCandidate(
            source_entity_id=source_id,
            match_entity_id=match_id,
            similarity_score=0.95,
            match_method="exact_id",
        )
    ]

    created = await create_candidates(db_session, org_id, "customer", source_id, candidates)
    assert len(created) == 1
    assert created[0].status == "auto_linked"


@pytest.mark.asyncio
async def test_create_candidates_mid_queued(db_session) -> None:
    """Mid-confidence matches are queued for review."""
    org_id = uuid.uuid4()
    source_id = uuid.uuid4()
    match_id = uuid.uuid4()

    candidates = [
        MatchCandidate(
            source_entity_id=source_id,
            match_entity_id=match_id,
            similarity_score=0.65,
            match_method="fuzzy_name",
        )
    ]

    created = await create_candidates(db_session, org_id, "customer", source_id, candidates)
    assert len(created) == 1
    assert created[0].status == "pending"


@pytest.mark.asyncio
async def test_create_candidates_low_not_created(db_session) -> None:
    """Low-confidence matches are not created."""
    org_id = uuid.uuid4()
    source_id = uuid.uuid4()
    match_id = uuid.uuid4()

    candidates = [
        MatchCandidate(
            source_entity_id=source_id,
            match_entity_id=match_id,
            similarity_score=0.30,
            match_method="fuzzy_name",
        )
    ]

    created = await create_candidates(db_session, org_id, "customer", source_id, candidates)
    assert len(created) == 0


@pytest.mark.asyncio
async def test_confirm_and_reject(db_session) -> None:
    """Confirm and reject operations work correctly."""
    from app.models.entity_resolution import EntityResolutionCandidate

    org_id = uuid.uuid4()
    reviewer_id = uuid.uuid4()

    # Create a pending candidate
    erc = EntityResolutionCandidate(
        organization_id=org_id,
        source_entity_type="customer",
        source_entity_id=uuid.uuid4(),
        match_entity_type="customer",
        match_entity_id=uuid.uuid4(),
        similarity_score=0.70,
        match_method="fuzzy_name",
        status="pending",
    )
    db_session.add(erc)
    await db_session.flush()

    # Confirm it
    confirmed = await confirm_match(db_session, org_id, erc.id, reviewer_id, notes="Looks same")
    assert confirmed is not None
    assert confirmed.status == "confirmed"
    assert confirmed.reviewed_by == reviewer_id

    # Create another pending candidate
    erc2 = EntityResolutionCandidate(
        organization_id=org_id,
        source_entity_type="customer",
        source_entity_id=uuid.uuid4(),
        match_entity_type="customer",
        match_entity_id=uuid.uuid4(),
        similarity_score=0.60,
        match_method="fuzzy_name",
        status="pending",
    )
    db_session.add(erc2)
    await db_session.flush()

    # Reject it
    rejected = await reject_match(
        db_session, org_id, erc2.id, reviewer_id, notes="Different company"
    )
    assert rejected is not None
    assert rejected.status == "rejected"


@pytest.mark.asyncio
async def test_cross_tenant_isolation(db_session) -> None:
    """Org A's candidates are not visible to Org B."""
    from app.models.entity_resolution import EntityResolutionCandidate

    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    # Create candidate for Org A
    erc = EntityResolutionCandidate(
        organization_id=org_a,
        source_entity_type="customer",
        source_entity_id=uuid.uuid4(),
        match_entity_type="customer",
        match_entity_id=uuid.uuid4(),
        similarity_score=0.70,
        match_method="fuzzy_name",
        status="pending",
    )
    db_session.add(erc)
    await db_session.flush()

    # Org B should see no candidates
    b_candidates = await get_pending_candidates(db_session, org_b)
    assert len(b_candidates) == 0

    # Org A should see 1
    a_candidates = await get_pending_candidates(db_session, org_a)
    assert len(a_candidates) == 1
