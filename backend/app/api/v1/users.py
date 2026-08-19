"""User management endpoints.

- POST /users — invite a new user (Owner/Admin only)
- PATCH /users/{id}/role — change a user's role (Owner/Admin only)

Organization_id is ALWAYS derived from the authenticated user's JWT —
never accepted from client input (ADR-003).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.rbac import require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.organization import Role, User

router = APIRouter(prefix="/users", tags=["users"])


# --- Request/Response Models ---


class InviteUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    role_name: str = "Viewer"


class ChangeRoleRequest(BaseModel):
    role_name: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
    role_name: str | None

    model_config = {"from_attributes": True}


# --- Endpoints ---


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("users", "write"))],
)
async def invite_user(
    req: InviteUserRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Invite a new user to the organization. Owner/Admin only (enforced by RBAC)."""
    # Check email uniqueness within org
    existing = await db.execute(
        select(User).where(
            User.organization_id == current_user.organization_id,
            User.email == req.email,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists in the organization",
        )

    # Find the requested role
    role_result = await db.execute(
        select(Role).where(
            Role.organization_id == current_user.organization_id,
            Role.name == req.role_name,
        )
    )
    role = role_result.scalar_one_or_none()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{req.role_name}' not found in this organization",
        )

    # Create user with organization_id from JWT (never from request)
    user = User(
        organization_id=current_user.organization_id,
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role_id=role.id,
    )
    db.add(user)
    await db.flush()

    # Audit
    audit = AuditLog(
        organization_id=current_user.organization_id,
        event_type="user.invited",
        entity_type="user",
        entity_id=user.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        description=f"User {req.email} invited with role {req.role_name}",
    )
    db.add(audit)
    await db.commit()

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        role_name=role.name,
    )


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("users", "write"))],
)
async def change_user_role(
    user_id: uuid.UUID,
    req: ChangeRoleRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Change a user's role. Owner/Admin only (enforced by RBAC)."""
    # Find the target user within the same org
    target = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_user.organization_id,
        )
    )
    target_user = target.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Find the new role
    role_result = await db.execute(
        select(Role).where(
            Role.organization_id == current_user.organization_id,
            Role.name == req.role_name,
        )
    )
    new_role = role_result.scalar_one_or_none()
    if new_role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{req.role_name}' not found in this organization",
        )

    old_role_name = "unknown"
    if target_user.role_id:
        old_role_result = await db.execute(select(Role).where(Role.id == target_user.role_id))
        old_role = old_role_result.scalar_one_or_none()
        if old_role:
            old_role_name = old_role.name

    target_user.role_id = new_role.id

    # Audit
    audit = AuditLog(
        organization_id=current_user.organization_id,
        event_type="user.role_changed",
        entity_type="user",
        entity_id=target_user.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        description=f"Role changed from {old_role_name} to {req.role_name}",
        event_metadata={"old_role": old_role_name, "new_role": req.role_name},
    )
    db.add(audit)
    await db.commit()

    return UserResponse(
        id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        is_active=target_user.is_active,
        role_name=new_role.name,
    )
