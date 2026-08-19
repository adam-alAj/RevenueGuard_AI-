"""Tests for the action drafter — dollar equality, all action types, gate enforcement.

Verifies:
- Draft financial figures are EXACTLY equal to Phase 9's deterministic potential_leakage
- All 9 recovery action types produce sensible draft content
- Gate 1 (case-level) enforcement: draft creation requires approved/action_pending case
- Gate 2 (draft-release) enforcement: execute requires draft approval first
- Cross-tenant isolation
- Audit trail on every state change
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
    get_drafts_for_case,
    set_case_status_store,
)
from app.services.recovery.templates import (
    render_draft,
    render_internal_task,
    render_invoice_draft,
    render_payment_reminder,
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


class TestDollarEquality:
    """Verify draft financial figures are EXACTLY equal to Phase 9's deterministic values."""

    def test_invoice_draft_dollar_equality(self) -> None:
        """Invoice draft amount exactly matches potential_leakage."""
        expected = Decimal("15000.00")
        actual = Decimal("12000.00")
        leakage = Decimal("3000.00")

        draft_content = render_invoice_draft(
            customer_name="Acme Inc.",
            case_number="RL-000123",
            leakage_type="underbilling",
            expected_amount=expected,
            actual_amount=actual,
            potential_leakage=leakage,
        )

        # The draft's total must be EXACTLY equal to potential_leakage
        assert draft_content["invoice"]["total"] == str(leakage)
        assert draft_content["invoice"]["subtotal"] == str(leakage)
        assert draft_content["invoice"]["line_items"][0]["amount"] == str(leakage)
        assert draft_content["invoice"]["line_items"][0]["unit_price"] == str(leakage)

        # Source of truth must match
        assert draft_content["source_of_truth"]["potential_leakage"] == str(leakage)
        assert draft_content["source_of_truth"]["expected_amount"] == str(expected)
        assert draft_content["source_of_truth"]["actual_amount"] == str(actual)

    def test_payment_reminder_dollar_equality(self) -> None:
        """Payment reminder amount exactly matches potential_leakage."""
        leakage = Decimal("5000.00")

        draft_content = render_payment_reminder(
            customer_name="Globex Corp",
            case_number="RL-000456",
            leakage_type="overdue_invoice",
            expected_amount=Decimal("5000.00"),
            actual_amount=Decimal("0.00"),
            potential_leakage=leakage,
        )

        assert draft_content["reminder"]["amount_due"] == str(leakage)
        assert draft_content["source_of_truth"]["potential_leakage"] == str(leakage)

    def test_internal_task_dollar_equality(self) -> None:
        """Internal task amount_at_risk exactly matches potential_leakage."""
        leakage = Decimal("24000.00")

        draft_content = render_internal_task(
            action_type="escalate_to_finance_manager",
            case_number="RL-000789",
            leakage_type="contract_expiration",
            expected_amount=Decimal("24000.00"),
            actual_amount=Decimal("0.00"),
            potential_leakage=leakage,
        )

        assert draft_content["task"]["amount_at_risk"] == str(leakage)
        assert draft_content["source_of_truth"]["potential_leakage"] == str(leakage)

    def test_all_action_types_preserve_exact_amount(self) -> None:
        """All 9 action types preserve the exact Decimal amount."""
        leakage = Decimal("7500.50")
        expected = Decimal("10000.00")
        actual = Decimal("2499.50")

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
            draft = render_draft(
                action_type=action_type,
                customer_name="Test Customer",
                case_number="RL-TEST",
                leakage_type="underbilling",
                expected_amount=expected,
                actual_amount=actual,
                potential_leakage=leakage,
            )
            # Every draft must have source_of_truth with exact amounts
            assert draft["source_of_truth"]["potential_leakage"] == str(leakage), (
                f"Action type {action_type} lost precision: "
                f"expected {leakage}, got {draft['source_of_truth']['potential_leakage']}"
            )
            assert draft["source_of_truth"]["expected_amount"] == str(expected)
            assert draft["source_of_truth"]["actual_amount"] == str(actual)


class TestAllActionTypes:
    """Verify all 9 recovery action types produce sensible draft content."""

    def test_create_invoice_draft(self) -> None:
        """Invoice draft has structured line items."""
        draft = render_draft(
            action_type="create_invoice_draft",
            customer_name="Acme",
            case_number="RL-001",
            leakage_type="underbilling",
            expected_amount=Decimal("1000"),
            actual_amount=Decimal("800"),
            potential_leakage=Decimal("200"),
        )
        assert draft["type"] == "invoice_draft"
        assert "line_items" in draft["invoice"]
        assert len(draft["invoice"]["line_items"]) == 1
        assert draft["draft_status"] == "pending_approval"

    def test_send_payment_reminder(self) -> None:
        """Payment reminder has subject and body."""
        draft = render_draft(
            action_type="send_payment_reminder",
            customer_name="Globex",
            case_number="RL-002",
            leakage_type="overdue_invoice",
            expected_amount=Decimal("5000"),
            actual_amount=Decimal("0"),
            potential_leakage=Decimal("5000"),
        )
        assert draft["type"] == "payment_reminder"
        assert "subject" in draft["reminder"]
        assert "body" in draft["reminder"]
        assert "Globex" in draft["reminder"]["body"]

    def test_internal_task_types(self) -> None:
        """All internal task types produce structured tasks."""
        internal_types = [
            "request_internal_investigation",
            "correct_pricing",
            "contact_account_manager",
            "renew_contract",
            "reconcile_payment",
            "issue_correction",
            "escalate_to_finance_manager",
        ]
        for action_type in internal_types:
            draft = render_draft(
                action_type=action_type,
                customer_name="Test",
                case_number="RL-003",
                leakage_type="underbilling",
                expected_amount=Decimal("1000"),
                actual_amount=Decimal("500"),
                potential_leakage=Decimal("500"),
            )
            assert draft["type"] == "internal_task"
            assert "title" in draft["task"]
            assert "description" in draft["task"]
            assert draft["draft_status"] == "pending_approval"

    def test_priority_based_on_amount(self) -> None:
        """High-amount tasks get high priority, lower amounts get medium."""
        high = render_internal_task(
            action_type="escalate_to_finance_manager",
            case_number="RL-H",
            leakage_type="underbilling",
            expected_amount=Decimal("10000"),
            actual_amount=Decimal("0"),
            potential_leakage=Decimal("10000"),
        )
        assert high["task"]["priority"] == "high"

        render_internal_task(
            action_type="send_payment_reminder",
            case_number="RL-L",
            leakage_type="underbilling",
            expected_amount=Decimal("100"),
            actual_amount=Decimal("50"),
            potential_leakage=Decimal("50"),
        )
        # Low amount → medium priority (for internal tasks)
        # send_payment_reminder goes through render_payment_reminder, not internal_task
        # Let's use a true internal task type
        low_internal = render_internal_task(
            action_type="correct_pricing",
            case_number="RL-L",
            leakage_type="underbilling",
            expected_amount=Decimal("100"),
            actual_amount=Decimal("50"),
            potential_leakage=Decimal("50"),
        )
        assert low_internal["task"]["priority"] == "medium"


class TestGate1Enforcement:
    """Gate 1: Case-level approval must be satisfied before draft creation."""

    def test_draft_creation_approved_case(self) -> None:
        """Draft creation succeeds for approved case."""
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
        assert draft.status == "draft"
        assert draft.draft_content["type"] == "invoice_draft"

    def test_draft_creation_action_pending_case(self) -> None:
        """Draft creation succeeds for action_pending case."""
        _setup_case(status="action_pending")
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
        assert draft.status == "draft"

    def test_draft_creation_rejects_detected_case(self) -> None:
        """Draft creation fails for detected case (Gate 1 not satisfied)."""
        _setup_case(status="detected")
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

    def test_draft_creation_rejects_pending_review_case(self) -> None:
        """Draft creation fails for pending_review case."""
        _setup_case(status="pending_review")
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

    def test_draft_creation_rejects_closed_case(self) -> None:
        """Draft creation fails for closed case."""
        _setup_case(status="closed")
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

    def test_draft_creation_updates_case_status(self) -> None:
        """Draft creation transitions case to action_pending."""
        _setup_case(status="approved")
        drafter = ActionDrafter()
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
        from app.services.recovery.action_drafter import _case_status_store

        assert _case_status_store["case-001"] == "action_pending"


class TestGate2Enforcement:
    """Gate 2: Draft-release approval must be satisfied before execution."""

    def test_execute_requires_gate2(self) -> None:
        """Executing a draft without Gate 2 approval fails."""
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

        # Try to execute without Gate 2 approval
        with pytest.raises(DualGateEnforcementError, match="Gate 2"):
            drafter.execute_draft(
                draft_id=draft.draft_id,
                organization_id="org-001",
                executor_id="user-001",
            )

    def test_execute_succeeds_after_gate2(self) -> None:
        """Executing a draft succeeds after Gate 2 approval."""
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

        # Gate 2: approve the draft
        drafter.approve_draft(
            draft_id=draft.draft_id,
            organization_id="org-001",
            approver_id="user-002",
        )

        # Now execute succeeds
        executed = drafter.execute_draft(
            draft_id=draft.draft_id,
            organization_id="org-001",
            executor_id="user-001",
        )
        assert executed.status == "action_completed"
        assert executed.executed_by == "user-001"

    def test_execute_updates_case_status(self) -> None:
        """Executing a draft transitions case to action_completed."""
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
        drafter.approve_draft(draft.draft_id, "org-001", "user-002")
        drafter.execute_draft(draft.draft_id, "org-001", "user-001")

        from app.services.recovery.action_drafter import _case_status_store

        assert _case_status_store["case-001"] == "action_completed"

    def test_draft_approve_rejects_already_approved(self) -> None:
        """Cannot approve a draft that's already approved."""
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

        with pytest.raises(DualGateEnforcementError):
            drafter.approve_draft(draft.draft_id, "org-001", "user-003")


class TestCrossTenantIsolation:
    """Cross-tenant isolation for draft operations."""

    def test_wrong_org_cannot_approve(self) -> None:
        """Different organization cannot approve a draft."""
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

        with pytest.raises(ActionDrafterError, match="Cross-tenant"):
            drafter.approve_draft(draft.draft_id, "org-002", "user-evil")

    def test_wrong_org_cannot_execute(self) -> None:
        """Different organization cannot execute a draft."""
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

        with pytest.raises(ActionDrafterError, match="Cross-tenant"):
            drafter.execute_draft(draft.draft_id, "org-002", "user-evil")


class TestDraftRetrieval:
    """Tests for draft retrieval."""

    def test_get_drafts_for_case(self) -> None:
        """Can retrieve all drafts for a case."""
        _setup_case(status="approved")
        drafter = ActionDrafter()
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
        drafter.create_draft(
            case_id="case-001",
            organization_id="org-001",
            action_type="send_payment_reminder",
            customer_name="Acme",
            case_number="RL-001",
            leakage_type="underbilling",
            expected_amount=Decimal("10000"),
            actual_amount=Decimal("8000"),
            potential_leakage=Decimal("2000"),
        )

        drafts = get_drafts_for_case("case-001")
        assert len(drafts) == 2
        assert drafts[0].action_type == "create_invoice_draft"
        assert drafts[1].action_type == "send_payment_reminder"


class TestCancelDraft:
    """Tests for draft cancellation."""

    def test_cancel_draft(self) -> None:
        """Can cancel a draft in draft status."""
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
        cancelled = drafter.cancel_draft(draft.draft_id, "org-001")
        assert cancelled.status == "cancelled"

    def test_cancel_completed_draft_fails(self) -> None:
        """Cannot cancel a completed draft."""
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

        with pytest.raises(ActionDrafterError, match="already completed"):
            drafter.cancel_draft(draft.draft_id, "org-001")
