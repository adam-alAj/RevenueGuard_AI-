"""Entity resolution API endpoints.

- GET /entity-resolution/pending — list pending resolution candidates
- POST /entity-resolution/{id}/confirm — confirm a match
- POST /entity-resolution/{id}/reject — reject a match
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.rbac import require_permission
from app.db.session import get_db
from app.models.organization import User
from app.services.resolution.review_queue import (
    confirm_match,
    get_pending_candidates,
    reject_match,
)

router = APIRouter(prefix="/entity-resolution", tags=["entity-resolution"])


# --- Response Models ---


class CandidateResponse(BaseModel):
    id: uuid.UUID
    source_entity_type: str
    source_entity_id: uuid.UUID
    match_entity_type: str
    match_entity_id: uuid.UUID
    similarity_score: float
    match_method: str
    status: str
    comparison_details: dict | None = None

    model_config = {"from_attributes": True}


class PendingResponse(BaseModel):
    total: int
    offset: int
    limit: int
    candidates: list[CandidateResponse]


class ReviewRequest(BaseModel):
    notes: str | None = None


# --- Endpoints ---


@router.get(
    "/pending",
    response_model=PendingResponse,
    dependencies=[Depends(require_permission("customers", "read"))],
)
async def list_pending(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PendingResponse:
    """List pending entity resolution candidates for review."""
    candidates = await get_pending_candidates(
        db=db,
        org_id=current_user.organization_id,
        offset=offset,
        limit=limit,
    )
    return PendingResponse(
        total=len(candidates),
        offset=offset,
        limit=limit,
        candidates=[CandidateResponse.model_validate(c) for c in candidates],
    )


@router.post(
    "/{candidate_id}/confirm",
    response_model=CandidateResponse,
    dependencies=[Depends(require_permission("customers", "write"))],
)
async def confirm(
    candidate_id: uuid.UUID,
    req: ReviewRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CandidateResponse:
    """Confirm an entity resolution match."""
    candidate = await confirm_match(
        db=db,
        org_id=current_user.organization_id,
        candidate_id=candidate_id,
        reviewer_id=current_user.id,
        notes=req.notes,
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found or already reviewed",
        )
    return CandidateResponse.model_validate(candidate)


@router.post(
    "/{candidate_id}/reject",
    response_model=CandidateResponse,
    dependencies=[Depends(require_permission("customers", "write"))],
)
async def reject(
    candidate_id: uuid.UUID,
    req: ReviewRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CandidateResponse:
    """Reject an entity resolution match."""
    candidate = await reject_match(
        db=db,
        org_id=current_user.organization_id,
        candidate_id=candidate_id,
        reviewer_id=current_user.id,
        notes=req.notes,
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found or already reviewed",
        )
    return CandidateResponse.model_validate(candidate)
