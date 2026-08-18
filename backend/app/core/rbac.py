"""Role-Based Access Control dependency.

require_permission("resource", "action") returns a dependency that:
1. Loads the user's role and its permissions from the database.
2. Checks if the required (resource, action) pair is in the role's permissions.
3. Raises 403 if not authorized.

This must be used on every endpoint that performs a write or sensitive read.
The permission matrix is seeded by Alembic migration 0002.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.organization import User


def require_permission(resource: str, action: str):
    """Return a dependency that enforces a specific permission check.

    Usage:
        @router.post("/invoices", dependencies=[Depends(require_permission("invoices", "write"))])
        async def create_invoice(...): ...
    """

    async def _check_permission(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        # Reload user with role + permissions eagerly loaded
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(User)
            .options(selectinload(User.role).selectinload("permissions"))
            .where(User.id == current_user.id)
        )
        user_with_role = result.scalar_one()
        if not user_with_role or not user_with_role.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No role assigned",
            )

        # Check if any permission matches (resource="*" means full access)
        for perm in user_with_role.role.permissions:
            if perm.resource == resource and perm.action == action:
                return user_with_role
            if perm.resource == "*" and perm.action == "*":
                return user_with_role

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {resource}:{action}",
        )

    return _check_permission
