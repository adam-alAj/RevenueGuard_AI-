"""Authentication endpoints.

- POST /auth/register — create Organization + first User (Owner role)
- POST /auth/login — email/password → access + refresh tokens
- POST /auth/refresh — refresh token → new access token (rotation)
- POST /auth/logout — revoke refresh token (stub — in-memory for MVP)
- POST /auth/password-reset-request — generate reset token (stub)
- POST /auth/password-reset-confirm — apply new password (stub)
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import (
    rate_limit_login,
    rate_limit_password_reset,
    rate_limit_register,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.organization import Organization, Role, User

router = APIRouter(prefix="/auth", tags=["auth"])

# --- In-memory refresh token store (MVP — replace with Redis/DB in production) ---
_refresh_tokens: dict[str, uuid.UUID] = {}  # jti -> user_id


# --- Request/Response Models ---

class RegisterRequest(BaseModel):
    organization_name: str
    organization_slug: str
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


# --- Endpoints ---

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rate: None = Depends(rate_limit_register),
) -> TokenResponse:
    """Register a new organization with the first user as Owner."""
    # Check slug uniqueness
    existing = await db.execute(
        select(Organization).where(Organization.slug == req.organization_slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already taken",
        )

    # Create organization
    org = Organization(name=req.organization_name, slug=req.organization_slug)
    db.add(org)
    await db.flush()

    # Create Owner role for this org
    owner_role = Role(
        organization_id=org.id,
        name="Owner",
        description="Full access to the organization",
    )
    db.add(owner_role)
    await db.flush()

    # Create user
    user = User(
        organization_id=org.id,
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role_id=owner_role.id,
    )
    db.add(user)
    await db.flush()

    # Generate tokens
    access_token = create_access_token(user.id, org.id, owner_role.name)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token jti
    refresh_payload = decode_token(refresh_token)
    _refresh_tokens[refresh_payload["jti"]] = user.id

    # Audit log
    audit = AuditLog(
        organization_id=org.id,
        event_type="user.register",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        actor_email=user.email,
        description=f"User registered as Owner of {org.name}",
    )
    db.add(audit)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rate: None = Depends(rate_limit_login),
) -> TokenResponse:
    """Authenticate with email/password, return access + refresh tokens."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(req.password, user.hashed_password):
        # Audit failed login (don't reveal which field was wrong)
        if user:
            audit = AuditLog(
                organization_id=user.organization_id,
                event_type="user.login_failed",
                entity_type="user",
                entity_id=user.id,
                actor_id=user.id,
                actor_email=user.email,
                description="Failed login attempt — invalid password",
            )
            db.add(audit)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Load role name
    role_name = "unknown"
    if user.role_id:
        role_result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = role_result.scalar_one_or_none()
        if role:
            role_name = role.name

    access_token = create_access_token(user.id, user.organization_id, role_name)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token jti
    refresh_payload = decode_token(refresh_token)
    _refresh_tokens[refresh_payload["jti"]] = user.id

    # Audit successful login
    audit = AuditLog(
        organization_id=user.organization_id,
        event_type="user.login",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        actor_email=user.email,
        description="Successful login",
    )
    db.add(audit)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> TokenResponse:
    """Exchange a refresh token for a new access + refresh token pair (rotation)."""
    try:
        payload = decode_token(req.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    jti = payload.get("jti")
    user_id = payload.get("sub")

    # Check if token has been used (rotation: each refresh token is single-use)
    if jti not in _refresh_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or already used",
        )

    # Invalidate the old refresh token
    del _refresh_tokens[jti]

    # Load user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    # Load role name
    role_name = "unknown"
    if user.role_id:
        role_result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = role_result.scalar_one_or_none()
        if role:
            role_name = role.name

    # Issue new token pair
    access_token = create_access_token(user.id, user.organization_id, role_name)
    refresh_token = create_refresh_token(user.id)

    new_refresh_payload = decode_token(refresh_token)
    _refresh_tokens[new_refresh_payload["jti"]] = user.id

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(req: RefreshRequest) -> None:
    """Revoke a refresh token (invalidate it so it cannot be used again)."""
    try:
        payload = decode_token(req.refresh_token)
        jti = payload.get("jti")
        _refresh_tokens.pop(jti, None)
    except Exception:
        # Even if token is invalid, logout is idempotent
        pass


@router.post("/password-reset-request", status_code=status.HTTP_202_ACCEPTED)
async def password_reset_request(
    req: PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rate: None = Depends(rate_limit_password_reset),
) -> dict[str, str]:
    """Request a password reset — generates a reset token (stub for MVP).

    In production, this would send an email with the reset link.
    Always returns 202 to avoid revealing whether the email exists.
    """
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if user:
        # Generate a password-reset token (short-lived, 1 hour)
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        from app.core.config import get_settings

        settings = get_settings()
        now = datetime.now(UTC)
        reset_payload = {
            "sub": str(user.id),
            "type": "password_reset",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "jti": str(uuid.uuid4()),
        }
        reset_token = pyjwt.encode(reset_payload, settings.JWT_SECRET, algorithm="HS256")

        # Audit
        audit = AuditLog(
            organization_id=user.organization_id,
            event_type="user.password_reset_requested",
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            actor_email=user.email,
            description="Password reset requested",
        )
        db.add(audit)
        await db.commit()

        # In production: send reset_token via email
        # For MVP: return it in the response (would be removed in production)
        return {"message": "If the email exists, a reset link has been sent.", "token": reset_token}

    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/password-reset-confirm", status_code=status.HTTP_200_OK)
async def password_reset_confirm(
    req: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Confirm a password reset with a valid token and set a new password."""
    import jwt as pyjwt

    from app.core.config import get_settings

    settings = get_settings()
    try:
        payload = pyjwt.decode(req.token, settings.JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from None

    if payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    user.hashed_password = hash_password(req.new_password)

    audit = AuditLog(
        organization_id=user.organization_id,
        event_type="user.password_reset_completed",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        actor_email=user.email,
        description="Password reset completed",
    )
    db.add(audit)
    await db.commit()

    return {"message": "Password has been reset successfully"}
