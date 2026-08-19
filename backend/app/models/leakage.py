"""Revenue leakage case, evidence, and investigation models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDMixin
from app.db.enums import CaseStatus, EvidenceType, LeakageType, Severity


class RevenueLeakageCase(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A detected instance of revenue leakage with full lifecycle tracking."""

    __tablename__ = "revenue_leakage_cases"
    __table_args__ = (
        Index("ix_rlc_org_case_number", "organization_id", "case_number", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    case_number: Mapped[str] = mapped_column(String(20), nullable=False)
    leakage_type: Mapped[LeakageType] = mapped_column(
        String(50), nullable=False
    )
    status: Mapped[CaseStatus] = mapped_column(
        String(50), nullable=False, default=CaseStatus.detected.value
    )
    severity: Mapped[Severity | None] = mapped_column(String(20), nullable=True)

    # Linked entities
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=True, index=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )

    # Financial impact
    expected_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    actual_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    potential_leakage: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    recoverable_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Confidence & scoring
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    confidence_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rule_versions.id"), nullable=True, index=True
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    snoozed_until: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class Evidence(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """An immutable, point-in-time snapshot supporting a leakage case."""

    __tablename__ = "evidence"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_leakage_cases.id"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(String(50), nullable=False)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Immutable snapshot — JSONB, never updated after creation
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Investigation(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A structured inquiry into a detected leakage case."""

    __tablename__ = "investigations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_leakage_cases.id"),
        nullable=False,
        index=True,
    )
    classification: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    agent_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_executions.id"), nullable=True
    )
