"""Recovery action API endpoints — draft viewing and dual approval gates.

Endpoints:
- POST /api/v1/recovery/{case_id}/create — Create a draft recovery action
- GET /api/v1/recovery/{case_id} — View draft for a case
- POST /api/v1/recovery/{draft_id}/approve — Gate 2: approve draft for manual action
- POST /api/v1/recovery/{draft_id}/execute — Human confirms they acted on the draft
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.rbac import require_permission
from app.services.recovery.action_drafter import (
    ActionDrafter,
    ActionDrafterError,
    DualGateEnforcementError,
    get_draft,
    get_drafts_for_case,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recovery", tags=["recovery"])

_drafter = ActionDrafter()


# --- Request/Response models ---


class CreateDraftRequest(BaseModel):
    """Request body for creating a recovery action draft."""

    action_type: str = Field(description="Recovery action type")
    customer_name: str = Field(description="Customer name")
    case_number: str = Field(description="Case reference number")
    leakage_type: str = Field(description="Type of leakage")
    expected_amount: str = Field(description="Expected amount (Decimal string)")
    actual_amount: str = Field(description="Actual amount (Decimal string)")
    potential_leakage: str = Field(description="Leakage amount (Decimal string)")
    rationale: str = Field(default="", description="Why this action was recommended")
    currency: str = Field(default="USD", description="ISO 4217 currency code")


class DraftResponse(BaseModel):
    """Response for draft operations."""

    draft_id: str
    case_id: str
    action_type: str
    status: str
    draft_content: dict
    rationale: str = ""
    draft_approved_by: str | None = None
    executed_by: str | None = None
    message: str = ""


class DraftListItem(BaseModel):
    """Summary of a draft for list views."""

    draft_id: str
    action_type: str
    status: str
    created_at: float


# --- Endpoints ---


@router.post("/{case_id}/create", response_model=DraftResponse)
async def create_draft(
    case_id: str,
    request: CreateDraftRequest,
    user: Any = Depends(require_permission("leakage", "execute")),
) -> DraftResponse:
    """Create a draft recovery action.

    Requires Gate 1: case must be in 'approved' or 'action_pending' status.
    """
    org_id = str(user.get("organization_id", ""))

    try:
        from decimal import Decimal

        draft = _drafter.create_draft(
            case_id=case_id,
            organization_id=org_id,
            action_type=request.action_type,
            customer_name=request.customer_name,
            case_number=request.case_number,
            leakage_type=request.leakage_type,
            expected_amount=Decimal(request.expected_amount),
            actual_amount=Decimal(request.actual_amount),
            potential_leakage=Decimal(request.potential_leakage),
            rationale=request.rationale,
            currency=request.currency,
        )
    except ActionDrafterError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return DraftResponse(
        draft_id=draft.draft_id,
        case_id=draft.case_id,
        action_type=draft.action_type,
        status=draft.status,
        draft_content=draft.draft_content,
        rationale=draft.rationale,
        message="Draft created. Requires Gate 2 (draft-release approval) before execution.",
    )


@router.get("/{case_id}", response_model=list[DraftListItem])
async def get_drafts(
    case_id: str,
    user: Any = Depends(require_permission("leakage", "read")),
) -> list[DraftListItem]:
    """View all drafts for a case."""
    org_id = str(user.get("organization_id", ""))
    drafts = get_drafts_for_case(case_id)
    # Filter by org
    org_drafts = [d for d in drafts if d.organization_id == org_id]
    return [
        DraftListItem(
            draft_id=d.draft_id,
            action_type=d.action_type,
            status=d.status,
            created_at=d.created_at,
        )
        for d in org_drafts
    ]


@router.get("/draft/{draft_id}", response_model=DraftResponse)
async def get_draft_detail(
    draft_id: str,
    user: Any = Depends(require_permission("leakage", "read")),
) -> DraftResponse:
    """View a specific draft's full content."""
    org_id = str(user.get("organization_id", ""))
    draft = get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft not found: {draft_id}")
    if draft.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Draft not found")

    return DraftResponse(
        draft_id=draft.draft_id,
        case_id=draft.case_id,
        action_type=draft.action_type,
        status=draft.status,
        draft_content=draft.draft_content,
        rationale=draft.rationale,
        draft_approved_by=draft.draft_approved_by,
        executed_by=draft.executed_by,
    )


@router.post("/{draft_id}/approve", response_model=DraftResponse)
async def approve_draft(
    draft_id: str,
    user: Any = Depends(require_permission("leakage", "approve")),
) -> DraftResponse:
    """Gate 2: Approve a draft for manual action.

    This is a SEPARATE approval from the case-level approval in Phase 10.
    Transitions draft from 'draft' to 'ready_for_manual_action'.
    """
    org_id = str(user.get("organization_id", ""))
    actor_id = str(user.get("user_id", ""))

    try:
        draft = _drafter.approve_draft(
            draft_id=draft_id,
            organization_id=org_id,
            approver_id=actor_id,
            approver_email=user.get("email"),
        )
    except DualGateEnforcementError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ActionDrafterError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return DraftResponse(
        draft_id=draft.draft_id,
        case_id=draft.case_id,
        action_type=draft.action_type,
        status=draft.status,
        draft_content=draft.draft_content,
        draft_approved_by=draft.draft_approved_by,
        message="Draft approved (Gate 2). Ready for manual action.",
    )


@router.post("/{draft_id}/execute", response_model=DraftResponse)
async def execute_draft(
    draft_id: str,
    user: Any = Depends(require_permission("leakage", "execute")),
) -> DraftResponse:
    """Human confirms they manually acted on the draft.

    Transitions draft from 'ready_for_manual_action' to 'action_completed'.
    Both approval gates must be satisfied before this can succeed.
    """
    org_id = str(user.get("organization_id", ""))
    actor_id = str(user.get("user_id", ""))

    try:
        draft = _drafter.execute_draft(
            draft_id=draft_id,
            organization_id=org_id,
            executor_id=actor_id,
            executor_email=user.get("email"),
        )
    except DualGateEnforcementError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ActionDrafterError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return DraftResponse(
        draft_id=draft.draft_id,
        case_id=draft.case_id,
        action_type=draft.action_type,
        status=draft.status,
        draft_content=draft.draft_content,
        executed_by=draft.executed_by,
        message="Action confirmed as executed. Case updated to action_completed.",
    )
