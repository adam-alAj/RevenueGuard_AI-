"""Rules API endpoints.

- POST /rules/run — manually trigger rule evaluation
- GET /rules — list all rules
- PUT /rules/{id} — update a rule (toggle active, change name)
- GET /rules/{id}/versions — list rule versions
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.rbac import require_permission
from app.db.session import get_db
from app.models.organization import User
from app.models.rule import Rule, RuleVersion
from app.rules.engine import run_rules

router = APIRouter(prefix="/rules", tags=["rules"])


# --- Response Models ---


class RuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    leakage_type: str
    is_active: bool
    model_config = {"from_attributes": True}


class RuleVersionResponse(BaseModel):
    id: uuid.UUID
    version: int
    parameters: dict
    description: str | None
    is_active: bool
    model_config = {"from_attributes": True}


class RuleUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class RunResponse(BaseModel):
    rules_evaluated: int
    cases_found: int
    case_ids: list[uuid.UUID]


# --- Endpoints ---


@router.post(
    "/run",
    response_model=RunResponse,
    dependencies=[Depends(require_permission("rules", "write"))],
)
async def trigger_rules(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    rule_types: str | None = None,
) -> RunResponse:
    """Manually trigger rule evaluation for the organization."""
    types = rule_types.split(",") if rule_types else None
    cases = await run_rules(
        db=db,
        org_id=current_user.organization_id,
        rule_types=types,
    )
    return RunResponse(
        rules_evaluated=len({c.leakage_type for c in cases}),
        cases_found=len(cases),
        case_ids=[c.id for c in cases],
    )


@router.get(
    "",
    response_model=list[RuleResponse],
    dependencies=[Depends(require_permission("rules", "read"))],
)
async def list_rules(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RuleResponse]:
    """List all rules for the organization."""
    result = await db.execute(
        select(Rule).where(Rule.organization_id == current_user.organization_id)
    )
    return [RuleResponse.model_validate(r) for r in result.scalars().all()]


@router.put(
    "/{rule_id}",
    response_model=RuleResponse,
    dependencies=[Depends(require_permission("rules", "write"))],
)
async def update_rule(
    rule_id: uuid.UUID,
    req: RuleUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RuleResponse:
    """Update a rule (toggle active, change name)."""
    result = await db.execute(
        select(Rule).where(
            Rule.id == rule_id,
            Rule.organization_id == current_user.organization_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    if req.name is not None:
        rule.name = req.name
    if req.is_active is not None:
        rule.is_active = req.is_active

    await db.commit()
    return RuleResponse.model_validate(rule)


@router.get(
    "/{rule_id}/versions",
    response_model=list[RuleVersionResponse],
    dependencies=[Depends(require_permission("rules", "read"))],
)
async def list_rule_versions(
    rule_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RuleVersionResponse]:
    """List all versions for a rule."""
    # Verify rule exists and belongs to this org
    rule_result = await db.execute(
        select(Rule).where(
            Rule.id == rule_id,
            Rule.organization_id == current_user.organization_id,
        )
    )
    if rule_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    result = await db.execute(
        select(RuleVersion)
        .where(RuleVersion.rule_id == rule_id)
        .order_by(RuleVersion.version.desc())
    )
    return [RuleVersionResponse.model_validate(v) for v in result.scalars().all()]
