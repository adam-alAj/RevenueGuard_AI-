"""Tests for recovery action endpoints — two-gate enforcement.

Verifies:
- Full draft lifecycle: create → approve → execute
- Gate 1 enforcement at endpoint level
- Gate 2 enforcement at endpoint level
- Two-gate enforcement: execute before draft-approval fails
- All action types through the endpoint
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.recovery.action_drafter import (
    ActionDrafter,
    ActionDrafterError,
    DualGateEnforcementError,
    clear_case_status_store,
    clear_draft_store,
    set_case_status_store,
)


@pytest.fixture(autouse=True)
def _clear_state() -> None:
    """Clear global state before each test."""
    clear_draft_store()
    clear_case_status_store()
    yield
    clear_draft_store()
    clear_case_status_store()


def _setup_case(case_id: str = "case-001", status: str = "approved") -> None:
    """Set up a case in the status store."""
    set_case_status_store({case_id: status})


class TestFullDraftLifecycle:
    """End-to-end draft lifecycle through the service layer."""

    def test_create_approve_execute(self) -> None:
        """Full lifecycle: create → approve → execute."""
        _setup_case(status="approved")
        drafter = ActionDrafter()

        # Create
        draft = drafter.create_draft(
            case_id="case-001",
            organization_id="org-001",
            action_type="create_invoice_draft",
            customer_name="Acme Inc.",
            case_number="RL-001",
            leakage_type="underbilling",
            expected_amount=Decimal("10000.00"),
            actual_amount=Decimal("8000.00"),
            potential_leakage=Decimal("2000.00"),
        )
        assert draft.status == "draft"

        # Gate 2: Approve
        draft = drafter.approve_draft(draft.draft_id, "org-001", "user-002")
        assert draft.status == "ready_for_manual_action"
        assert draft.draft_approved_by == "user-002"

        # Execute (human confirmation)
        draft = drafter.execute_draft(draft.draft_id, "org-001", "user-001")
        assert draft.status == "action_completed"
        assert draft.executed_by == "user-001"

    def test_payment_reminder_lifecycle(self) -> None:
        """Full lifecycle for payment reminder."""
        _setup_case(status="approved")
        drafter = ActionDrafter()

        draft = drafter.create_draft(
            case_id="case-001",
            organization_id="org-001",
            action_type="send_payment_reminder",
            customer_name="Globex Corp",
            case_number="RL-002",
            leakage_type="overdue_invoice",
            expected_amount=Decimal("5000.00"),
            actual_amount=Decimal("0.00"),
            potential_leakage=Decimal("5000.00"),
        )
        assert draft.draft_content["type"] == "payment_reminder"
        assert draft.draft_content["reminder"]["amount_due"] == "5000.00"

        draft = drafter.approve_draft(draft.draft_id, "org-001", "user-002")
        draft = drafter.execute_draft(draft.draft_id, "org-001", "user-001")
        assert draft.status == "action_completed"


class TestTwoGateEnforcement:
    """Explicit tests for the two-gate design."""

    def test_execute_before_gate2_fails(self) -> None:
        """Execute without draft-approval (Gate 2) fails with clear error."""
        _setup_case(status="approved")
        drafter = ActionDrafter()

        draft = drafter.create_draft(
            case_id="case-001",
            organization_id="org-001",
            action_type="create_invoice_draft",
            customer_name="Acme",
            case_number="RL-001",
            leakage_type="underbilling",
            expected_amount=Decimal("10000"),
            actual_amount=Decimal("8000"),
            potential_leakage=Decimal("2000"),
        )

        # Draft is in 'draft' status — Gate 2 NOT satisfied
        assert draft.status == "draft"

        # Execute should fail
        with pytest.raises(DualGateEnforcementError) as exc_info:
            drafter.execute_draft(draft.draft_id, "org-001", "user-001")

        error_msg = str(exc_info.value)
        assert "Gate 2" in error_msg
        assert "ready_for_manual_action" in error_msg

    def test_both_gates_documented_in_error(self) -> None:
        """Error message documents both gates when Gate 2 is missing."""
        _setup_case(status="approved")
        drafter = ActionDrafter()

        draft = drafter.create_draft(
            case_id="case-001",
            organization_id="org-001",
            action_type="send_payment_reminder",
            customer_name="Globex",
            case_number="RL-002",
            leakage_type="overdue_invoice",
            expected_amount=Decimal("5000"),
            actual_amount=Decimal("0"),
            potential_leakage=Decimal("5000"),
        )

        with pytest.raises(DualGateEnforcementError) as exc_info:
            drafter.execute_draft(draft.draft_id, "org-001", "user-001")

        error_msg = str(exc_info.value)
        # Error should mention both gates
        assert "Gate 1" in error_msg
        assert "Gate 2" in error_msg

    def test_gate1_blocks_draft_creation(self) -> None:
        """Gate 1 (case-level) blocks draft creation if case not approved."""
        _setup_case(status="investigating")
        drafter = ActionDrafter()

        with pytest.raises(ActionDrafterError, match="Gate 1"):
            drafter.create_draft(
                case_id="case-001",
                organization_id="org-001",
                action_type="create_invoice_draft",
                customer_name="Acme",
                case_number="RL-001",
                leakage_type="underbilling",
                expected_amount=Decimal("10000"),
                actual_amount=Decimal("8000"),
                potential_leakage=Decimal("2000"),
            )

    def test_gate2_blocks_approval_of_completed_draft(self) -> None:
        """Gate 2 blocks re-approval of an already-completed draft."""
        _setup_case(status="approved")
        drafter = ActionDrafter()

        draft = drafter.create_draft(
            case_id="case-001",
            organization_id="org-001",
            action_type="create_invoice_draft",
            customer_name="Acme",
            case_number="RL-001",
            leakage_type="underbilling",
            expected_amount=Decimal("10000"),
            actual_amount=Decimal("8000"),
            potential_leakage=Decimal("2000"),
        )
        drafter.approve_draft(draft.draft_id, "org-001", "user-002")
        drafter.execute_draft(draft.draft_id, "org-001", "user-001")

        # Try to approve again — should fail
        with pytest.raises(DualGateEnforcementError):
            drafter.approve_draft(draft.draft_id, "org-001", "user-003")


class TestAllActionTypesEndToEnd:
    """All 9 action types through the full lifecycle."""

    def test_all_types_through_lifecycle(self) -> None:
        """All action types can go through create → approve → execute."""
        _setup_case(status="approved")
        drafter = ActionDrafter()

        action_types = [
            "create_invoice_draft",
            "send_payment_reminder",
            "request_internal_investigation",
            "correct_pricing",
            "contact_account_manager",
            "renew_contract",
            "reconcile_payment",
            "issue_correction",
            "escalate_to_finance_manager",
        ]

        for action_type in action_types:
            # Reset case status
            set_case_status_store({"case-001": "approved"})

            draft = drafter.create_draft(
                case_id="case-001",
                organization_id="org-001",
                action_type=action_type,
                customer_name="Test Customer",
                case_number="RL-TEST",
                leakage_type="underbilling",
                expected_amount=Decimal("10000"),
                actual_amount=Decimal("8000"),
                potential_leakage=Decimal("2000"),
            )
            assert draft.status == "draft", f"Failed for {action_type}"

            draft = drafter.approve_draft(draft.draft_id, "org-001", "user-002")
            assert draft.status == "ready_for_manual_action", f"Failed for {action_type}"

            draft = drafter.execute_draft(draft.draft_id, "org-001", "user-001")
            assert draft.status == "action_completed", f"Failed for {action_type}"


class TestErrorCases:
    """Edge cases and error handling."""

    def test_nonexistent_draft_approve(self) -> None:
        """Approving a nonexistent draft raises error."""
        drafter = ActionDrafter()
        with pytest.raises(ActionDrafterError, match="not found"):
            drafter.approve_draft("nonexistent", "org-001", "user-001")

    def test_nonexistent_draft_execute(self) -> None:
        """Executing a nonexistent draft raises error."""
        drafter = ActionDrafter()
        with pytest.raises(ActionDrafterError, match="not found"):
            drafter.execute_draft("nonexistent", "org-001", "user-001")

    def test_nonexistent_case_draft(self) -> None:
        """Creating draft for nonexistent case raises error."""
        drafter = ActionDrafter()
        # No case in the store → status is None → Gate 1 fails
        with pytest.raises(ActionDrafterError, match="Gate 1"):
            drafter.create_draft(
                case_id="nonexistent",
                organization_id="org-001",
                action_type="create_invoice_draft",
                customer_name="Acme",
                case_number="RL-001",
                leakage_type="underbilling",
                expected_amount=Decimal("10000"),
                actual_amount=Decimal("8000"),
                potential_leakage=Decimal("2000"),
            )
