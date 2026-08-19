"""Verification API endpoints — recovery verification and metrics.

Endpoints:
- POST /api/v1/verification/{case_id}/reverify — Re-verify a case's recovery status
- POST /api/v1/verification/org/{org_id}/reverify-all — Verify all cases in an org
- GET /api/v1/verification/org/{org_id}/metrics — Get org-level recovery metrics
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.rbac import require_permission
from app.services.verification.metrics import (
    CaseMetricsInput,
    compute_org_metrics,
)
from app.services.verification.verification_executor import (
    VerificationExecutor,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["verification"])

_executor = VerificationExecutor()


# --- Request/Response models ---


class VerificationResponse(BaseModel):
    """Response for a verification check."""

    case_id: str
    verified: bool
    status: str
    matched_invoice_id: str | None = None
    matched_payment_id: str | None = None
    recovered_amount: str | None = None
    message: str = ""


class MetricsResponse(BaseModel):
    """Response for org-level metrics."""

    organization_id: str
    total_potential_leakage: str
    total_confirmed_leakage: str
    total_recovered_revenue: str
    open_cases: int
    critical_cases: int
    total_cases: int
    recovered_cases: int
    recovery_rate: str


class BatchVerificationResponse(BaseModel):
    """Response for batch verification."""

    organization_id: str
    cases_checked: int
    results: list[VerificationResponse]


# --- Endpoints ---


@router.post("/{case_id}/reverify", response_model=VerificationResponse)
async def reverify_case(
    case_id: str,
    user: Any = Depends(require_permission("leakage", "read")),
) -> VerificationResponse:
    """Re-verify a case's recovery status.

    Checks whether an action_completed case has actually resulted in
    recovered revenue by matching invoice and payment data.
    """
    result = _executor.check(case_id)

    return VerificationResponse(
        case_id=result.case_id,
        verified=result.verified,
        status=result.status,
        matched_invoice_id=result.matched_invoice_id,
        matched_payment_id=result.matched_payment_id,
        recovered_amount=str(result.recovered_amount) if result.recovered_amount else None,
        message=result.message,
    )


@router.post("/org/{org_id}/reverify-all", response_model=BatchVerificationResponse)
async def reverify_all_for_org(
    org_id: str,
    user: Any = Depends(require_permission("leakage", "read")),
) -> BatchVerificationResponse:
    """Re-verify all action_completed/verified cases in an organization.

    Auto-run this as part of every subsequent ingestion.
    """
    results = _executor.check_all_for_org(org_id)

    return BatchVerificationResponse(
        organization_id=org_id,
        cases_checked=len(results),
        results=[
            VerificationResponse(
                case_id=r.case_id,
                verified=r.verified,
                status=r.status,
                matched_invoice_id=r.matched_invoice_id,
                matched_payment_id=r.matched_payment_id,
                recovered_amount=str(r.recovered_amount) if r.recovered_amount else None,
                message=r.message,
            )
            for r in results
        ],
    )


@router.get("/org/{org_id}/metrics", response_model=MetricsResponse)
async def get_org_metrics(
    org_id: str,
    cases: list[CaseMetricsInput] | None = None,
    user: Any = Depends(require_permission("leakage", "read")),
) -> MetricsResponse:
    """Get org-level recovery metrics.

    In production, cases would be queried from the database.
    For MVP, cases are passed in the request body.
    """
    if cases is None:
        cases = []

    metrics = compute_org_metrics(org_id, cases)

    return MetricsResponse(
        organization_id=metrics.organization_id,
        total_potential_leakage=str(metrics.total_potential_leakage),
        total_confirmed_leakage=str(metrics.total_confirmed_leakage),
        total_recovered_revenue=str(metrics.total_recovered_revenue),
        open_cases=metrics.open_cases,
        critical_cases=metrics.critical_cases,
        total_cases=metrics.total_cases,
        recovered_cases=metrics.recovered_cases,
        recovery_rate=str(metrics.recovery_rate),
    )
