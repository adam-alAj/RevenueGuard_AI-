"""Leakage approval endpoints — human-in-the-loop case lifecycle actions.

Endpoints:
- POST /api/v1/leakage/{id}/approve — Approve a pending_review case
- POST /api/v1/leakage/{id}/reject — Reject with required reason
- POST /api/v1/leakage/{id}/assign — Assign to a user
- POST /api/v1/leakage/{id}/close — Close a case
- POST /api/v1/leakage/{id}/snooze — Snooze until a date
- POST /api/v1/leakage/{id}/request-evidence — Re-trigger investigation
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.rbac import require_permission
from app.services.approval_service import (
    ApprovalService,
)
from app.workflows.resume import WorkflowResumer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leakage", tags=["leakage-approval"])

# Shared service instances
_approval_service = ApprovalService()
_workflow_resumer: WorkflowResumer | None = None


def get_approval_service() -> ApprovalService:
    """Get the approval service singleton."""
    return _approval_service


def get_workflow_resumer(settings: Settings) -> WorkflowResumer:
    """Get or create the workflow resumer."""
    global _workflow_resumer
    if _workflow_resumer is None:
        _workflow_resumer = WorkflowResumer(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )
    return _workflow_resumer


# --- Request/Response models ---


class ApproveRequest(BaseModel):
    """Request body for approving a case."""

    reason: str | None = Field(default=None, description="Reason for approval")


class RejectRequest(BaseModel):
    """Request body for rejecting a case."""

    reason: str = Field(description="Required reason for rejection")


class AssignRequest(BaseModel):
    """Request body for assigning a case."""

    assigned_to: str = Field(description="UUID of the user to assign to")


class CloseRequest(BaseModel):
    """Request body for closing a case."""

    reason: str = Field(default="", description="Reason for closing")


class SnoozeRequest(BaseModel):
    """Request body for snoozing a case."""

    snoozed_until: str = Field(
        description="ISO 8601 datetime until which to snooze"
    )


class RequestEvidenceRequest(BaseModel):
    """Request body for requesting more evidence."""

    reason: str = Field(
        default="", description="Reason for requesting additional evidence"
    )


class CaseResponse(BaseModel):
    """Response for case state changes."""

    case_id: str
    status: str
    assigned_to: str | None = None
    snoozed_until: str | None = None
    message: str = ""


class AuditEntryResponse(BaseModel):
    """Response for audit log entries."""

    event_type: str
    entity_id: str
    actor_id: str | None = None
    description: str | None = None
    timestamp: float


# --- Endpoints ---


@router.post("/{case_id}/approve", response_model=CaseResponse)
async def approve_case(
    case_id: str,
    request: ApproveRequest,
    settings: Settings = Depends(get_settings),
    user: Any = Depends(require_permission("leakage", "approve")),
) -> CaseResponse:
    """Approve a pending_review case.

    RBAC: Finance Manager, Accountant, Admin, Owner only.
    Creates an Approval row and signals the workflow to resume.
    """
    org_id = str(user.get("organization_id", ""))
    actor_id = str(user.get("user_id", ""))
    actor_email = user.get("email")

    try:
        service = get_approval_service()
        case = service.approve(
            case_id=case_id,
            organization_id=org_id,
            actor_id=actor_id,
            actor_email=actor_email,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Signal workflow resume
    resumer = get_workflow_resumer(settings)
    resume_result = await resumer.resume_after_approval(
        case_id=case_id,
        organization_id=org_id,
        approved_action=None,  # Will be loaded from persisted state
        approval_reason=request.reason,
    )

    return CaseResponse(
        case_id=case.case_id,
        status=case.status,
        assigned_to=case.assigned_to,
        snoozed_until=case.snoozed_until,
        message=f"Case approved. {resume_result.message}",
    )


@router.post("/{case_id}/reject", response_model=CaseResponse)
async def reject_case(
    case_id: str,
    request: RejectRequest,
    settings: Settings = Depends(get_settings),
    user: Any = Depends(require_permission("leakage", "reject")),
) -> CaseResponse:
    """Reject a pending_review case. Requires a reason."""
    org_id = str(user.get("organization_id", ""))
    actor_id = str(user.get("user_id", ""))
    actor_email = user.get("email")

    try:
        service = get_approval_service()
        case = service.reject(
            case_id=case_id,
            organization_id=org_id,
            actor_id=actor_id,
            actor_email=actor_email,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return CaseResponse(
        case_id=case.case_id,
        status=case.status,
        message="Case rejected.",
    )


@router.post("/{case_id}/assign", response_model=CaseResponse)
async def assign_case(
    case_id: str,
    request: AssignRequest,
    user: Any = Depends(require_permission("leakage", "assign")),
) -> CaseResponse:
    """Assign a case to a user."""
    org_id = str(user.get("organization_id", ""))
    actor_id = str(user.get("user_id", ""))
    actor_email = user.get("email")

    try:
        service = get_approval_service()
        case = service.assign(
            case_id=case_id,
            organization_id=org_id,
            assigned_to=request.assigned_to,
            actor_id=actor_id,
            actor_email=actor_email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return CaseResponse(
        case_id=case.case_id,
        status=case.status,
        assigned_to=case.assigned_to,
        message=f"Case assigned to {request.assigned_to}.",
    )


@router.post("/{case_id}/close", response_model=CaseResponse)
async def close_case(
    case_id: str,
    request: CloseRequest,
    user: Any = Depends(require_permission("leakage", "close")),
) -> CaseResponse:
    """Close a case from any non-terminal status."""
    org_id = str(user.get("organization_id", ""))
    actor_id = str(user.get("user_id", ""))
    actor_email = user.get("email")

    try:
        service = get_approval_service()
        case = service.close(
            case_id=case_id,
            organization_id=org_id,
            actor_id=actor_id,
            actor_email=actor_email,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return CaseResponse(
        case_id=case.case_id,
        status=case.status,
        message="Case closed.",
    )


@router.post("/{case_id}/snooze", response_model=CaseResponse)
async def snooze_case(
    case_id: str,
    request: SnoozeRequest,
    user: Any = Depends(require_permission("leakage", "snooze")),
) -> CaseResponse:
    """Snooze a case until a specified date."""
    org_id = str(user.get("organization_id", ""))
    actor_id = str(user.get("user_id", ""))
    actor_email = user.get("email")

    try:
        service = get_approval_service()
        case = service.snooze(
            case_id=case_id,
            organization_id=org_id,
            snoozed_until=request.snoozed_until,
            actor_id=actor_id,
            actor_email=actor_email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return CaseResponse(
        case_id=case.case_id,
        status=case.status,
        snoozed_until=case.snoozed_until,
        message=f"Case snoozed until {request.snoozed_until}.",
    )


@router.post("/{case_id}/request-evidence", response_model=CaseResponse)
async def request_evidence(
    case_id: str,
    request: RequestEvidenceRequest,
    settings: Settings = Depends(get_settings),
    user: Any = Depends(require_permission("leakage", "investigate")),
) -> CaseResponse:
    """Request additional evidence — re-triggers Investigation Agent."""
    org_id = str(user.get("organization_id", ""))
    actor_id = str(user.get("user_id", ""))
    actor_email = user.get("email")

    try:
        service = get_approval_service()
        case = service.request_evidence(
            case_id=case_id,
            organization_id=org_id,
            actor_id=actor_id,
            actor_email=actor_email,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return CaseResponse(
        case_id=case.case_id,
        status=case.status,
        message="Evidence re-investigation triggered.",
    )
