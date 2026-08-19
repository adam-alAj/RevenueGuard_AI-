"""Tests for approval endpoints — RBAC, audit logging, and checkpoint-resume.

Verifies:
- Approve/reject/assign/close/snooze/request-evidence all work
- Illegal transitions are rejected
- AuditLog is written on every action
- Cross-tenant access is denied
- Workflow resume is signaled on approve
"""

from __future__ import annotations

import pytest

from app.services.approval_service import (
    ApprovalService,
    CaseState,
    clear_audit_log,
    clear_case_store,
    get_audit_log,
    get_case,
    set_case_store,
)
from app.services.case_state_machine import InvalidTransitionError
from app.workflows.resume import WorkflowResumer


@pytest.fixture(autouse=True)
def _clear_state() -> None:
    """Clear global state before each test."""
    clear_audit_log()
    clear_case_store()
    yield
    clear_audit_log()
    clear_case_store()


def _make_case(
    case_id: str = "case-001",
    org_id: str = "org-001",
    status: str = "pending_review",
) -> CaseState:
    """Create a test case in the store."""
    case = CaseState(
        case_id=case_id,
        organization_id=org_id,
        status=status,
    )
    store = {case_id: case}
    set_case_store(store)
    return case


class TestApprove:
    """Tests for case approval."""

    def test_approve_pending_review(self) -> None:
        """Approving a pending_review case transitions to approved."""
        _make_case(status="pending_review")
        service = ApprovalService()
        case = service.approve(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            actor_email="mgr@example.com",
            reason="Looks correct",
        )
        assert case.status == "approved"

    def test_approve_writes_audit_log(self) -> None:
        """Approval writes an AuditLog entry."""
        _make_case()
        service = ApprovalService()
        service.approve(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            actor_email="mgr@example.com",
            reason="Verified the numbers",
        )
        log = get_audit_log()
        assert len(log) == 1
        assert log[0].event_type == "case_approved"
        assert log[0].actor_id == "user-001"
        assert "Verified the numbers" in (log[0].description or "")

    def test_approve_rejects_non_pending_review(self) -> None:
        """Cannot approve a case that is not in pending_review."""
        _make_case(status="detected")
        service = ApprovalService()
        with pytest.raises(InvalidTransitionError):
            service.approve(
                case_id="case-001",
                organization_id="org-001",
                actor_id="user-001",
            )

    def test_approve_rejects_already_approved(self) -> None:
        """Cannot approve an already-approved case."""
        _make_case(status="approved")
        service = ApprovalService()
        with pytest.raises(InvalidTransitionError):
            service.approve(
                case_id="case-001",
                organization_id="org-001",
                actor_id="user-001",
            )

    def test_approve_rejects_closed_case(self) -> None:
        """Cannot approve a closed case."""
        _make_case(status="closed")
        service = ApprovalService()
        with pytest.raises(InvalidTransitionError):
            service.approve(
                case_id="case-001",
                organization_id="org-001",
                actor_id="user-001",
            )


class TestReject:
    """Tests for case rejection."""

    def test_reject_with_reason(self) -> None:
        """Rejecting with a reason transitions to rejected."""
        _make_case()
        service = ApprovalService()
        case = service.reject(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            reason="Numbers don't match our records",
        )
        assert case.status == "rejected"

    def test_reject_requires_reason(self) -> None:
        """Rejection without a reason raises ValueError."""
        _make_case()
        service = ApprovalService()
        with pytest.raises(ValueError, match="reason is required"):
            service.reject(
                case_id="case-001",
                organization_id="org-001",
                actor_id="user-001",
                reason="",
            )

    def test_reject_writes_audit_log(self) -> None:
        """Rejection writes an AuditLog entry."""
        _make_case()
        service = ApprovalService()
        service.reject(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            reason="Disputed amount",
        )
        log = get_audit_log()
        assert len(log) == 1
        assert log[0].event_type == "case_rejected"
        assert "Disputed amount" in (log[0].description or "")


class TestAssign:
    """Tests for case assignment."""

    def test_assign_case(self) -> None:
        """Assigning a case updates assigned_to."""
        _make_case()
        service = ApprovalService()
        case = service.assign(
            case_id="case-001",
            organization_id="org-001",
            assigned_to="user-002",
            actor_id="user-001",
        )
        assert case.assigned_to == "user-002"

    def test_assign_does_not_change_status(self) -> None:
        """Assignment does not change the case status."""
        _make_case(status="pending_review")
        service = ApprovalService()
        case = service.assign(
            case_id="case-001",
            organization_id="org-001",
            assigned_to="user-002",
            actor_id="user-001",
        )
        assert case.status == "pending_review"

    def test_assign_writes_audit_log(self) -> None:
        """Assignment writes an AuditLog entry."""
        _make_case()
        service = ApprovalService()
        service.assign(
            case_id="case-001",
            organization_id="org-001",
            assigned_to="user-002",
            actor_id="user-001",
        )
        log = get_audit_log()
        assert len(log) == 1
        assert log[0].event_type == "case_assigned"


class TestClose:
    """Tests for case closure."""

    def test_close_from_pending_review(self) -> None:
        """Closing from pending_review transitions to closed."""
        _make_case(status="pending_review")
        service = ApprovalService()
        case = service.close(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            reason="No longer relevant",
        )
        assert case.status == "closed"

    def test_close_from_detected(self) -> None:
        """Closing from detected transitions to closed."""
        _make_case(status="detected")
        service = ApprovalService()
        case = service.close(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
        )
        assert case.status == "closed"

    def test_close_rejects_already_closed(self) -> None:
        """Cannot close an already-closed case."""
        _make_case(status="closed")
        service = ApprovalService()
        with pytest.raises(InvalidTransitionError):
            service.close(
                case_id="case-001",
                organization_id="org-001",
                actor_id="user-001",
            )

    def test_close_writes_audit_log(self) -> None:
        """Closure writes an AuditLog entry."""
        _make_case()
        service = ApprovalService()
        service.close(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            reason="Resolved externally",
        )
        log = get_audit_log()
        assert len(log) == 1
        assert log[0].event_type == "case_closed"


class TestSnooze:
    """Tests for case snoozing."""

    def test_snooze_sets_date(self) -> None:
        """Snoozing sets snoozed_until."""
        _make_case()
        service = ApprovalService()
        case = service.snooze(
            case_id="case-001",
            organization_id="org-001",
            snoozed_until="2026-08-26T00:00:00",
            actor_id="user-001",
        )
        assert case.snoozed_until == "2026-08-26T00:00:00"

    def test_snooze_does_not_change_status(self) -> None:
        """Snoozing does not change the case status."""
        _make_case(status="detected")
        service = ApprovalService()
        case = service.snooze(
            case_id="case-001",
            organization_id="org-001",
            snoozed_until="2026-08-26T00:00:00",
            actor_id="user-001",
        )
        assert case.status == "detected"

    def test_snooze_invalid_date_rejected(self) -> None:
        """Invalid date format is rejected."""
        _make_case()
        service = ApprovalService()
        with pytest.raises(ValueError, match="Invalid snoozed_until"):
            service.snooze(
                case_id="case-001",
                organization_id="org-001",
                snoozed_until="not-a-date",
                actor_id="user-001",
            )

    def test_snooze_writes_audit_log(self) -> None:
        """Snoozing writes an AuditLog entry."""
        _make_case()
        service = ApprovalService()
        service.snooze(
            case_id="case-001",
            organization_id="org-001",
            snoozed_until="2026-08-26T00:00:00",
            actor_id="user-001",
        )
        log = get_audit_log()
        assert len(log) == 1
        assert log[0].event_type == "case_snoozed"


class TestRequestEvidence:
    """Tests for evidence re-investigation."""

    def test_request_evidence(self) -> None:
        """Requesting evidence transitions to investigating."""
        _make_case(status="pending_review")
        service = ApprovalService()
        case = service.request_evidence(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            reason="Need more documentation",
        )
        assert case.status == "investigating"

    def test_request_evidence_rejects_wrong_status(self) -> None:
        """Cannot request evidence from action_completed status."""
        _make_case(status="action_completed")
        service = ApprovalService()
        with pytest.raises(InvalidTransitionError):
            service.request_evidence(
                case_id="case-001",
                organization_id="org-001",
                actor_id="user-001",
            )

    def test_request_evidence_writes_audit_log(self) -> None:
        """Evidence request writes an AuditLog entry."""
        _make_case(status="pending_review")
        service = ApprovalService()
        service.request_evidence(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            reason="Missing contract amendment",
        )
        log = get_audit_log()
        assert len(log) == 1
        assert log[0].event_type == "case_evidence_requested"


class TestCrossTenantIsolation:
    """Tests for cross-tenant access denial."""

    def test_approve_wrong_org_denied(self) -> None:
        """Cannot approve a case from a different organization."""
        _make_case(org_id="org-001")
        service = ApprovalService()
        with pytest.raises(ValueError, match="Cross-tenant"):
            service.approve(
                case_id="case-001",
                organization_id="org-002",  # wrong org
                actor_id="user-001",
            )

    def test_reject_wrong_org_denied(self) -> None:
        """Cannot reject a case from a different organization."""
        _make_case(org_id="org-001")
        service = ApprovalService()
        with pytest.raises(ValueError, match="Cross-tenant"):
            service.reject(
                case_id="case-001",
                organization_id="org-002",
                actor_id="user-001",
                reason="test",
            )

    def test_close_wrong_org_denied(self) -> None:
        """Cannot close a case from a different organization."""
        _make_case(org_id="org-001")
        service = ApprovalService()
        with pytest.raises(ValueError, match="Cross-tenant"):
            service.close(
                case_id="case-001",
                organization_id="org-002",
                actor_id="user-001",
            )


class TestCaseNotFound:
    """Tests for case-not-found errors."""

    def test_approve_nonexistent(self) -> None:
        """Approving a nonexistent case raises ValueError."""
        service = ApprovalService()
        with pytest.raises(ValueError, match="not found"):
            service.approve(
                case_id="nonexistent",
                organization_id="org-001",
                actor_id="user-001",
            )

    def test_reject_nonexistent(self) -> None:
        """Rejecting a nonexistent case raises ValueError."""
        service = ApprovalService()
        with pytest.raises(ValueError, match="not found"):
            service.reject(
                case_id="nonexistent",
                organization_id="org-001",
                actor_id="user-001",
                reason="test",
            )


class TestWorkflowResume:
    """Tests for workflow resume signaling."""

    @pytest.mark.asyncio
    async def test_resume_after_approval(self) -> None:
        """Workflow resume returns success after approval."""
        resumer = WorkflowResumer(api_key="test-key")
        result = await resumer.resume_after_approval(
            case_id="case-001",
            organization_id="org-001",
            approved_action="create_invoice_draft",
            approval_reason="Verified",
        )
        assert result.success is True
        assert result.case_id == "case-001"
        assert result.action == "create_invoice_draft"
        assert "Phase 11" in result.message

    @pytest.mark.asyncio
    async def test_resume_records_action(self) -> None:
        """Resume result includes the approved action."""
        resumer = WorkflowResumer(api_key="test-key")
        result = await resumer.resume_after_approval(
            case_id="case-002",
            organization_id="org-001",
            approved_action="send_payment_reminder",
        )
        assert result.action == "send_payment_reminder"


class TestFullApprovalFlow:
    """End-to-end approval flow test."""

    def test_full_lifecycle(self) -> None:
        """Complete lifecycle: detected → investigating → pending_review → approved."""
        _make_case(status="detected")
        service = ApprovalService()

        # Move to investigating
        # (Not tested here since it's a state machine transition, not a service action)

        # Move to pending_review (simulated)
        case = get_case("case-001")
        assert case is not None
        case.status = "pending_review"

        # Approve
        case = service.approve(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            reason="Approved after review",
        )
        assert case.status == "approved"

        # Verify audit log has the approval
        log = get_audit_log()
        assert len(log) == 1
        assert log[0].event_type == "case_approved"

    def test_approve_then_close(self) -> None:
        """Approve then close a case."""
        _make_case(status="pending_review")
        service = ApprovalService()

        # Approve
        service.approve(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
        )

        # Close
        case = service.close(
            case_id="case-001",
            organization_id="org-001",
            actor_id="user-001",
            reason="Action completed externally",
        )
        assert case.status == "closed"

        # Two audit entries
        log = get_audit_log()
        assert len(log) == 2
        assert log[0].event_type == "case_approved"
        assert log[1].event_type == "case_closed"
