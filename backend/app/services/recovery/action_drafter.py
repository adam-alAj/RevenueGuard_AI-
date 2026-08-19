"""Action drafter — generates draft recovery artifacts with dual approval gates.

Two distinct approval gates:
1. Case-level approval (Phase 10): approves that the leakage case is real
2. Draft-release approval (Phase 11): approves that the specific draft artifact
   is correct and safe to release for manual action

These MUST be separate — collapsing them would let a single click trigger
a financial mistake.

Draft lifecycle:
  draft → ready_for_manual_action → action_completed

Status flow on RevenueLeakageCase:
  approved → action_pending (on draft creation)
  action_pending → action_completed (on human confirmation)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from app.services.recovery.templates import render_draft

logger = logging.getLogger(__name__)


# --- Draft statuses ---


DRAFT_STATUSES = {"draft", "ready_for_manual_action", "action_completed", "cancelled"}


# --- Draft state ---


@dataclass
class RecoveryDraft:
    """In-memory representation of a recovery action draft."""

    draft_id: str
    case_id: str
    organization_id: str
    action_type: str
    status: str = "draft"
    draft_content: dict = field(default_factory=dict)
    rationale: str = ""
    created_at: float = field(default_factory=time.time)
    draft_approved_by: str | None = None
    draft_approved_at: float | None = None
    executed_by: str | None = None
    executed_at: float | None = None


# In-memory stores (will be replaced with DB in production)
_draft_store: dict[str, RecoveryDraft] = {}
_case_status_store: dict[str, str] = {}


def set_draft_store(store: dict[str, RecoveryDraft]) -> None:
    """Set the draft store (for testing)."""
    global _draft_store
    _draft_store = store


def clear_draft_store() -> None:
    """Clear the draft store."""
    global _draft_store
    _draft_store = {}


def set_case_status_store(store: dict[str, str]) -> None:
    """Set the case status store (for testing)."""
    global _case_status_store
    _case_status_store = store


def clear_case_status_store() -> None:
    """Clear the case status store."""
    global _case_status_store
    _case_status_store = {}


def get_draft(draft_id: str) -> RecoveryDraft | None:
    """Get a draft by ID."""
    return _draft_store.get(draft_id)


def get_drafts_for_case(case_id: str) -> list[RecoveryDraft]:
    """Get all drafts for a case."""
    return [d for d in _draft_store.values() if d.case_id == case_id]


class ActionDrafterError(Exception):
    """Raised when draft operations fail."""


class DualGateEnforcementError(ActionDrafterError):
    """Raised when the dual approval gate is violated."""


class ActionDrafter:
    """Generates draft recovery artifacts with dual approval gate enforcement.

    Gate 1 (case-level): Already passed — case must be in 'approved' or
    'action_pending' status before a draft can be created.

    Gate 2 (draft-release): A separate, explicit approval that transitions
    the draft from 'draft' to 'ready_for_manual_action'. This is the gate
    that says "this specific draft artifact is correct and safe."

    Execute (human confirmation): After a human has manually performed the
    action outside the system, they confirm execution, transitioning the
    draft to 'action_completed'.
    """

    def create_draft(
        self,
        case_id: str,
        organization_id: str,
        action_type: str,
        customer_name: str,
        case_number: str,
        leakage_type: str,
        expected_amount: Decimal,
        actual_amount: Decimal,
        potential_leakage: Decimal,
        rationale: str = "",
        currency: str = "USD",
    ) -> RecoveryDraft:
        """Create a draft recovery action.

        Requires Gate 1: case must be in 'approved' or 'action_pending' status.

        Args:
            case_id: UUID of the case.
            organization_id: Tenant scope.
            action_type: Type of recovery action.
            customer_name: Customer name for templates.
            case_number: Case reference number.
            leakage_type: Type of leakage.
            expected_amount: Expected amount (from Phase 9).
            actual_amount: Actual amount (from Phase 9).
            potential_leakage: Leakage amount (from Phase 9).
            rationale: Why this action was recommended.
            currency: ISO 4217 currency code.

        Returns:
            RecoveryDraft with draft content.

        Raises:
            ActionDrafterError: If Gate 1 is not satisfied.
        """
        # Gate 1: Case must be approved or action_pending
        case_status = _case_status_store.get(case_id)
        if case_status not in ("approved", "action_pending"):
            raise ActionDrafterError(
                f"Cannot create draft for case {case_id}: "
                f"case status is '{case_status}', must be 'approved' or 'action_pending'. "
                f"Gate 1 (case-level approval) has not been satisfied."
            )

        # Generate draft content deterministically
        draft_content = render_draft(
            action_type=action_type,
            customer_name=customer_name,
            case_number=case_number,
            leakage_type=leakage_type,
            expected_amount=expected_amount,
            actual_amount=actual_amount,
            potential_leakage=potential_leakage,
            rationale=rationale,
            currency=currency,
        )

        draft_id = str(uuid.uuid4())
        draft = RecoveryDraft(
            draft_id=draft_id,
            case_id=case_id,
            organization_id=organization_id,
            action_type=action_type,
            status="draft",
            draft_content=draft_content,
            rationale=rationale,
        )

        _draft_store[draft_id] = draft

        # Update case status to action_pending
        _case_status_store[case_id] = "action_pending"

        logger.info(
            "Draft created: %s for case %s (action=%s)",
            draft_id,
            case_id,
            action_type,
        )

        return draft

    def approve_draft(
        self,
        draft_id: str,
        organization_id: str,
        approver_id: str,
        approver_email: str | None = None,
    ) -> RecoveryDraft:
        """Approve a draft for manual action (Gate 2).

        Transitions draft from 'draft' to 'ready_for_manual_action'.
        This is a SEPARATE approval from the case-level approval in Phase 10.

        Args:
            draft_id: UUID of the draft.
            organization_id: Tenant scope.
            approver_id: UUID of the user approving the draft.
            approver_email: Email of the approver.

        Returns:
            Updated RecoveryDraft.

        Raises:
            DualGateEnforcementError: If draft is not in 'draft' status.
        """
        draft = _draft_store.get(draft_id)
        if not draft:
            raise ActionDrafterError(f"Draft not found: {draft_id}")
        if draft.organization_id != organization_id:
            raise ActionDrafterError("Cross-tenant access denied")

        # Gate 2: Draft must be in 'draft' status
        if draft.status != "draft":
            raise DualGateEnforcementError(
                f"Cannot approve draft {draft_id}: status is '{draft.status}', "
                f"must be 'draft'. Draft-release approval (Gate 2) can only be "
                f"applied to drafts in 'draft' status."
            )

        draft.status = "ready_for_manual_action"
        draft.draft_approved_by = approver_id
        draft.draft_approved_at = time.time()

        logger.info(
            "Draft approved (Gate 2): %s by %s",
            draft_id,
            approver_id,
        )

        return draft

    def execute_draft(
        self,
        draft_id: str,
        organization_id: str,
        executor_id: str,
        executor_email: str | None = None,
    ) -> RecoveryDraft:
        """Mark a draft as executed after human confirmation.

        Transitions draft from 'ready_for_manual_action' to 'action_completed'.
        This is the human-confirmation step: a human confirms they manually
        performed the action outside the system.

        Args:
            draft_id: UUID of the draft.
            organization_id: Tenant scope.
            executor_id: UUID of the user confirming execution.
            executor_email: Email of the executor.

        Returns:
            Updated RecoveryDraft.

        Raises:
            DualGateEnforcementError: If draft is not ready for manual action.
        """
        draft = _draft_store.get(draft_id)
        if not draft:
            raise ActionDrafterError(f"Draft not found: {draft_id}")
        if draft.organization_id != organization_id:
            raise ActionDrafterError("Cross-tenant access denied")

        # Both gates must be satisfied: draft must be ready_for_manual_action
        if draft.status != "ready_for_manual_action":
            raise DualGateEnforcementError(
                f"Cannot execute draft {draft_id}: status is '{draft.status}', "
                f"must be 'ready_for_manual_action'. "
                f"Both approval gates must be satisfied before execution:\n"
                f"  Gate 1 (case-level): Case must be approved\n"
                f"  Gate 2 (draft-release): Draft must be approved\n"
                f"Current draft status indicates Gate 2 has not been completed."
            )

        draft.status = "action_completed"
        draft.executed_by = executor_id
        draft.executed_at = time.time()

        # Update case status to action_completed
        _case_status_store[draft.case_id] = "action_completed"

        logger.info(
            "Draft executed: %s by %s (case %s)",
            draft_id,
            executor_id,
            draft.case_id,
        )

        return draft

    def cancel_draft(
        self,
        draft_id: str,
        organization_id: str,
    ) -> RecoveryDraft:
        """Cancel a draft.

        Args:
            draft_id: UUID of the draft.
            organization_id: Tenant scope.

        Returns:
            Updated RecoveryDraft.
        """
        draft = _draft_store.get(draft_id)
        if not draft:
            raise ActionDrafterError(f"Draft not found: {draft_id}")
        if draft.organization_id != organization_id:
            raise ActionDrafterError("Cross-tenant access denied")

        if draft.status == "action_completed":
            raise ActionDrafterError(
                f"Cannot cancel draft {draft_id}: already completed."
            )

        draft.status = "cancelled"
        return draft
