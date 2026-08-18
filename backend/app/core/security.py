"""Password hashing and JWT token management.

Uses argon2 for password hashing (never bcrypt — argon2 is the OWASP recommendation).
Uses PyJWT for JWT creation/verification with HS256 algorithm.

Security invariants:
- Password hashes are NEVER returned in API responses.
- JWT_SECRET is NEVER logged or included in any output.
- Access tokens are short-lived (15 min). Refresh tokens are longer-lived (7 days).
- Refresh tokens are single-use with rotation — each refresh invalidates the old token.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# --- Password Hashing ---

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using argon2."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# --- JWT Tokens ---

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role_name: str,
) -> str:
    """Create a short-lived access token containing user identity and tenant context."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "role": role_name,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a longer-lived refresh token (single-use, rotated on each refresh)."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token.

    Raises jwt.InvalidTokenError on any failure — caller should catch
    and return 401.
    """
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
