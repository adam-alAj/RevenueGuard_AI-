"""Leakage API endpoints — investigation workflow trigger.

Endpoints:
- POST /api/v1/leakage/{id}/investigate — Trigger the investigation workflow
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.rbac import require_permission
from app.workflows.leakage_investigation_workflow import (
    LeakageInvestigationWorkflow,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leakage", tags=["leakage"])


class InvestigateRequest(BaseModel):
    """Request body for triggering an investigation."""

    case_id: str
    organization_id: str
    leakage_type: str
    contract_id: str | None = None
    invoice_id: str | None = None
    customer_id: str | None = None
    project_id: str | None = None
    expected_amount: float | None = None
    actual_amount: float | None = None


class StepResultResponse(BaseModel):
    """Response for a single workflow step."""

    step_name: str
    success: bool
    duration_ms: float
    error: str | None = None


class InvestigateResponse(BaseModel):
    """Response from the investigation workflow."""

    execution_id: str
    case_id: str
    status: str
    auto_closed: bool
    close_reason: str | None = None
    classification: str | None = None
    confidence: float | None = None
    recommended_action: str | None = None
    steps: list[StepResultResponse]
    total_duration_ms: float
    error: str | None = None


@router.post("/{case_id}/investigate", response_model=InvestigateResponse)
async def investigate_leakage_case(
    case_id: str,
    request: InvestigateRequest,
    settings: Settings = Depends(get_settings),
    _user: Any = Depends(require_permission("leakage", "investigate")),
) -> InvestigateResponse:
    """Trigger the investigation workflow for a leakage case.

    This endpoint starts the full investigation pipeline:
    CandidateIntake → ContractAnalysis → Investigation → branch →
    RecoveryRecommendation → HumanApprovalPause.

    The workflow is checkpointed so interrupted runs can be resumed.
    """
    if settings.APP_ENV == "production" and not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured. Cannot run AI agents.",
        )

    # Validate case_id matches URL parameter
    if case_id != request.case_id:
        raise HTTPException(
            status_code=400,
            detail="case_id in request body must match the URL parameter.",
        )

    workflow = LeakageInvestigationWorkflow(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
    )

    try:
        execution = await workflow.run(
            case_id=request.case_id,
            organization_id=request.organization_id,
            leakage_type=request.leakage_type,
            contract_id=request.contract_id,
            invoice_id=request.invoice_id,
            customer_id=request.customer_id,
            project_id=request.project_id,
            expected_amount=request.expected_amount,
            actual_amount=request.actual_amount,
        )
    except Exception as e:
        logger.error("Investigation workflow failed for case %s: %s", case_id, e)
        raise HTTPException(
            status_code=500,
            detail=f"Workflow execution failed: {type(e).__name__}: {e}",
        ) from e

    # Build response from execution
    state = execution.final_state
    steps = [
        StepResultResponse(
            step_name=s.step_name,
            success=s.success,
            duration_ms=s.duration_ms,
            error=s.error,
        )
        for s in execution.steps
    ]

    classification = None
    confidence = None
    recommended_action = None

    if state and state.investigation_result:
        classification = state.investigation_result.classification.value
        confidence = state.investigation_result.confidence

    if state and state.recovery_recommendation:
        recommended_action = state.recovery_recommendation.action.value

    return InvestigateResponse(
        execution_id=execution.execution_id,
        case_id=execution.case_id,
        status=state.status if state else "error",
        auto_closed=state.auto_closed if state else False,
        close_reason=state.close_reason if state else None,
        classification=classification,
        confidence=confidence,
        recommended_action=recommended_action,
        steps=steps,
        total_duration_ms=execution.total_duration_ms,
        error=state.error if state else None,
    )
