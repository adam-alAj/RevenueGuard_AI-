"""Entity resolution review queue management.

Handles the lifecycle of resolution candidates:
- Create candidates from matcher output
- List pending candidates
- Confirm a match (link the entities)
- Reject a match (unlink / mark as not the same)

All operations are tenant-scoped.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_resolution import EntityResolutionCandidate
from app.services.resolution.matcher import (
    classify_match,
)


async def create_candidates(
    db: AsyncSession,
    org_id: uuid.UUID,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    candidates: list,  # list of MatchCandidate
) -> list[EntityResolutionCandidate]:
    """Create EntityResolutionCandidate records from matcher output.

    Auto-links high-confidence matches. Queues mid-confidence for review.
    Ignores low-confidence matches.
    """
    created = []
    for candidate in candidates:
        band = classify_match(candidate.similarity_score)

        if band == "high":
            status = "auto_linked"
        elif band == "mid":
            status = "pending"
        else:
            continue  # Low confidence — don't create a candidate

        erc = EntityResolutionCandidate(
            organization_id=org_id,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            match_entity_type=source_entity_type,  # Same type for now
            match_entity_id=candidate.match_entity_id,
            similarity_score=candidate.similarity_score,
            match_method=candidate.match_method,
            status=status,
            comparison_details=candidate.comparison_details,
        )
        db.add(erc)
        created.append(erc)

    if created:
        await db.flush()
    return created


async def get_pending_candidates(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[EntityResolutionCandidate]:
    """Get pending resolution candidates for an organization."""
    result = await db.execute(
        select(EntityResolutionCandidate)
        .where(
            EntityResolutionCandidate.organization_id == org_id,
            EntityResolutionCandidate.status == "pending",
        )
        .order_by(EntityResolutionCandidate.similarity_score.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def confirm_match(
    db: AsyncSession,
    org_id: uuid.UUID,
    candidate_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    notes: str | None = None,
) -> EntityResolutionCandidate | None:
    """Confirm a resolution candidate — mark as confirmed.

    Returns the updated candidate, or None if not found.
    """
    result = await db.execute(
        select(EntityResolutionCandidate).where(
            EntityResolutionCandidate.id == candidate_id,
            EntityResolutionCandidate.organization_id == org_id,
            EntityResolutionCandidate.status == "pending",
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        return None

    candidate.status = "confirmed"
    candidate.reviewed_by = reviewer_id
    candidate.review_notes = notes
    await db.flush()
    return candidate


async def reject_match(
    db: AsyncSession,
    org_id: uuid.UUID,
    candidate_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    notes: str | None = None,
) -> EntityResolutionCandidate | None:
    """Reject a resolution candidate — mark as rejected.

    Returns the updated candidate, or None if not found.
    """
    result = await db.execute(
        select(EntityResolutionCandidate).where(
            EntityResolutionCandidate.id == candidate_id,
            EntityResolutionCandidate.organization_id == org_id,
            EntityResolutionCandidate.status == "pending",
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        return None

    candidate.status = "rejected"
    candidate.reviewed_by = reviewer_id
    candidate.review_notes = notes
    await db.flush()
    return candidate
