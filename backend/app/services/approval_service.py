"""Approval service — implements case lifecycle actions with audit logging.

Every action:
1. Validates the state machine transition
2. Applies the change to the case
3. Writes an AuditLog row
4. Returns the result

Actions:
- approve: Approve a pending_review case (requires FM/Accountant/Admin/Owner)
- reject: Reject a pending_review case with a reason
- assign: Assign a case to a user
- close: Close a case from any non-terminal status
- snooze: Set snoozed_until to exclude from inbox
- request_evidence: Re-trigger a scoped Investigation Agent re-run
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from app.services.case_state_machine import (
    validate_transition,
)

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """An audit log entry written on every case action."""

    event_type: str
    entity_type: str
    entity_id: str
    organization_id: str
    actor_id: str | None = None
    actor_email: str | None = None
    description: str | None = None
    event_metadata: dict | None = None
    timestamp: float = field(default_factory=time.time)


# In-memory audit log (will be replaced with DB writes in production)
_audit_log: list[AuditEntry] = []


def get_audit_log() -> list[AuditEntry]:
    """Return the in-memory audit log."""
    return _audit_log


def clear_audit_log() -> None:
    """Clear the in-memory audit log (for testing)."""
    _audit_log.clear()


def _write_audit(
    event_type: str,
    entity_id: str,
    organization_id: str,
    actor_id: str | None = None,
    actor_email: str | None = None,
    description: str | None = None,
    metadata: dict | None = None,
) -> AuditEntry:
    """Write an audit log entry."""
    entry = AuditEntry(
        event_type=event_type,
        entity_type="RevenueLeakageCase",
        entity_id=entity_id,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_email=actor_email,
        description=description,
        event_metadata=metadata,
    )
    _audit_log.append(entry)
    logger.info(
        "Audit: %s on case %s by %s (%s)",
        event_type,
        entity_id,
        actor_id or "system",
        description or "",
    )
    return entry


@dataclass
class CaseState:
    """In-memory representation of a case's mutable state.

    In production, this would be backed by the database.
    """

    case_id: str
    organization_id: str
    status: str = "detected"
    assigned_to: str | None = None
    snoozed_until: str | None = None
    description: str | None = None


# In-memory case store (will be replaced with DB in production)
_case_store: dict[str, CaseState] = {}


def set_case_store(store: dict[str, CaseState]) -> None:
    """Set the case store (for testing)."""
    global _case_store
    _case_store = store


def clear_case_store() -> None:
    """Clear the case store."""
    global _case_store
    _case_store = {}


def get_case(case_id: str) -> CaseState | None:
    """Get a case by ID."""
    return _case_store.get(case_id)


def _update_case(case: CaseState, **kwargs: object) -> None:
    """Update case fields."""
    for key, value in kwargs.items():
        if hasattr(case, key):
            setattr(case, key, value)


class ApprovalService:
    """Service for case lifecycle actions with state machine enforcement."""

    def approve(
        self,
        case_id: str,
        organization_id: str,
        actor_id: str,
        actor_email: str | None = None,
        reason: str | None = None,
    ) -> CaseState:
        """Approve a pending_review case.

        Transitions: pending_review → approved

        Args:
            case_id: UUID of the case.
            organization_id: Tenant scope.
            actor_id: UUID of the user approving.
            actor_email: Email of the approver (for audit).
            reason: Optional reason for approval.

        Returns:
            Updated CaseState.

        Raises:
            InvalidTransitionError: If case is not in pending_review.
            ValueError: If case not found.
        """
        case = _case_store.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")
        if case.organization_id != organization_id:
            raise ValueError("Cross-tenant access denied")

        validate_transition(case.status, "approved")

        _update_case(case, status="approved")

        _write_audit(
            event_type="case_approved",
            entity_id=case_id,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_email=actor_email,
            description=reason or "Case approved",
            metadata={"decision": "approved", "reason": reason},
        )

        return case

    def reject(
        self,
        case_id: str,
        organization_id: str,
        actor_id: str,
        actor_email: str | None = None,
        reason: str = "",
    ) -> CaseState:
        """Reject a pending_review case.

        Transitions: pending_review → rejected

        Args:
            case_id: UUID of the case.
            organization_id: Tenant scope.
            actor_id: UUID of the user rejecting.
            actor_email: Email of the rejector.
            reason: Required reason for rejection.

        Returns:
            Updated CaseState.

        Raises:
            InvalidTransitionError: If case is not in pending_review.
            ValueError: If case not found or reason is empty.
        """
        if not reason:
            raise ValueError("Rejection reason is required")

        case = _case_store.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")
        if case.organization_id != organization_id:
            raise ValueError("Cross-tenant access denied")

        validate_transition(case.status, "rejected")

        _update_case(case, status="rejected")

        _write_audit(
            event_type="case_rejected",
            entity_id=case_id,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_email=actor_email,
            description=reason,
            metadata={"decision": "rejected", "reason": reason},
        )

        return case

    def assign(
        self,
        case_id: str,
        organization_id: str,
        assigned_to: str,
        actor_id: str,
        actor_email: str | None = None,
    ) -> CaseState:
        """Assign a case to a user.

        Does not change status — only updates the assigned_to field.

        Args:
            case_id: UUID of the case.
            organization_id: Tenant scope.
            assigned_to: UUID of the user to assign to.
            actor_id: UUID of the user making the assignment.
            actor_email: Email of the assigner.

        Returns:
            Updated CaseState.
        """
        case = _case_store.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")
        if case.organization_id != organization_id:
            raise ValueError("Cross-tenant access denied")

        _update_case(case, assigned_to=assigned_to)

        _write_audit(
            event_type="case_assigned",
            entity_id=case_id,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_email=actor_email,
            description=f"Assigned to {assigned_to}",
            metadata={"assigned_to": assigned_to},
        )

        return case

    def close(
        self,
        case_id: str,
        organization_id: str,
        actor_id: str,
        actor_email: str | None = None,
        reason: str = "",
    ) -> CaseState:
        """Close a case from any non-terminal status.

        Transitions: [any non-terminal] → closed

        Args:
            case_id: UUID of the case.
            organization_id: Tenant scope.
            actor_id: UUID of the user closing.
            actor_email: Email of the closer.
            reason: Reason for closing.

        Returns:
            Updated CaseState.
        """
        case = _case_store.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")
        if case.organization_id != organization_id:
            raise ValueError("Cross-tenant access denied")

        validate_transition(case.status, "closed")

        _update_case(case, status="closed")

        _write_audit(
            event_type="case_closed",
            entity_id=case_id,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_email=actor_email,
            description=reason or "Case closed",
            metadata={"reason": reason},
        )

        return case

    def snooze(
        self,
        case_id: str,
        organization_id: str,
        snoozed_until: str,
        actor_id: str,
        actor_email: str | None = None,
    ) -> CaseState:
        """Snooze a case until a specified date.

        Sets snoozed_until to exclude the case from the default inbox.
        Does not change status.

        Args:
            case_id: UUID of the case.
            organization_id: Tenant scope.
            snoozed_until: ISO datetime string until which to snooze.
            actor_id: UUID of the user snoozing.
            actor_email: Email of the snoozer.

        Returns:
            Updated CaseState.
        """
        case = _case_store.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")
        if case.organization_id != organization_id:
            raise ValueError("Cross-tenant access denied")

        # Validate the date format
        try:
            datetime.fromisoformat(snoozed_until)
        except ValueError as e:
            raise ValueError(
                f"Invalid snoozed_until format: {snoozed_until}. "
                "Use ISO 8601 format (e.g., 2026-08-26T00:00:00)."
            ) from e

        _update_case(case, snoozed_until=snoozed_until)

        _write_audit(
            event_type="case_snoozed",
            entity_id=case_id,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_email=actor_email,
            description=f"Snoozed until {snoozed_until}",
            metadata={"snoozed_until": snoozed_until},
        )

        return case

    def request_evidence(
        self,
        case_id: str,
        organization_id: str,
        actor_id: str,
        actor_email: str | None = None,
        reason: str = "",
    ) -> CaseState:
        """Request additional evidence for a case.

        Re-triggers a scoped Investigation Agent re-run.
        Transitions: pending_review → investigating

        Args:
            case_id: UUID of the case.
            organization_id: Tenant scope.
            actor_id: UUID of the user requesting evidence.
            actor_email: Email of the requester.
            reason: Reason for requesting more evidence.

        Returns:
            Updated CaseState.
        """
        case = _case_store.get(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")
        if case.organization_id != organization_id:
            raise ValueError("Cross-tenant access denied")

        validate_transition(case.status, "investigating")

        _update_case(case, status="investigating")

        _write_audit(
            event_type="case_evidence_requested",
            entity_id=case_id,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_email=actor_email,
            description=reason or "Additional evidence requested",
            metadata={"reason": reason},
        )

        return case
