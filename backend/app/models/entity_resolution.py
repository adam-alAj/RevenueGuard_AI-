"""Entity resolution candidate model.

Tracks potential matches between entities for human review.
Each candidate records the source entity, the proposed match, a similarity
score, and the resolution status (pending/confirmed/rejected).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class EntityResolutionCandidate(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A potential entity match awaiting human review or auto-resolution."""

    __tablename__ = "entity_resolution_candidates"
    __table_args__ = (
        Index("ix_erc_org_source", "organization_id", "source_entity_type", "source_entity_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    # Source entity (the new/imported record)
    source_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Proposed match (the existing record it might be the same as)
    match_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    match_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Similarity scoring
    similarity_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    match_method: Mapped[str] = mapped_column(String(50), nullable=False)

    # Status: pending, confirmed, rejected, auto_linked
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    # Review details
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Context: what fields were compared
    comparison_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
