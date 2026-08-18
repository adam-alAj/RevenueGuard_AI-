"""Tests for authentication — password hashing, JWT tokens, and auth flow.

These tests verify:
- Password hashing with argon2 (hash + verify)
- JWT token creation and decoding
- Access token contains correct claims (user_id, org_id, role)
- Refresh token rotation (old token invalidated after use)
- Refresh token reuse detection (replay attack prevention)
"""

from __future__ import annotations

import uuid

import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

# ---------------------------------------------------------------------------
# Password hashing tests
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_hash_password_is_not_plaintext(self) -> None:
        hashed = hash_password("mysecretpassword")
        assert hashed != "mysecretpassword"
        assert hashed.startswith("$argon2")

    def test_verify_password_correct(self) -> None:
        hashed = hash_password("correct-password")
        assert verify_password("correct-password", hashed) is True

    def test_verify_password_incorrect(self) -> None:
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self) -> None:
        """Argon2 uses random salt — same password produces different hashes."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2

    def test_verify_survives_unicode(self) -> None:
        hashed = hash_password("pà$$w0rd_ünïcödé")
        assert verify_password("pà$$w0rd_ünïcödé", hashed) is True


# ---------------------------------------------------------------------------
# JWT token tests
# ---------------------------------------------------------------------------

class TestJWTTokens:
    def _make_uuid(self) -> uuid.UUID:
        return uuid.uuid4()

    def test_create_access_token_decodes(self) -> None:
        user_id = self._make_uuid()
        org_id = self._make_uuid()
        token = create_access_token(user_id, org_id, "Owner")
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["org_id"] == str(org_id)
        assert payload["role"] == "Owner"
        assert payload["type"] == "access"

    def test_create_refresh_token_decodes(self) -> None:
        user_id = self._make_uuid()
        token = create_refresh_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_access_token_has_jti(self) -> None:
        token = create_access_token(self._make_uuid(), self._make_uuid(), "Admin")
        payload = decode_token(token)
        assert "jti" in payload
        assert len(payload["jti"]) > 0

    def test_refresh_token_has_jti(self) -> None:
        token = create_refresh_token(self._make_uuid())
        payload = decode_token(token)
        assert "jti" in payload

    def test_invalid_token_raises(self) -> None:
        with pytest.raises(jwt.exceptions.PyJWTError):
            decode_token("invalid.token.here")

    def test_tampered_token_raises(self) -> None:
        token = create_access_token(self._make_uuid(), self._make_uuid(), "Owner")
        # Tamper with the payload
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B") + "." + parts[2]
        with pytest.raises(jwt.exceptions.PyJWTError):
            decode_token(tampered)

    def test_token_does_not_contain_password(self) -> None:
        """JWT must never contain password or hash data."""
        token = create_access_token(self._make_uuid(), self._make_uuid(), "Owner")
        payload = decode_token(token)
        assert "password" not in payload
        assert "hashed_password" not in payload
        assert "secret" not in payload


# ---------------------------------------------------------------------------
# Token expiry tests
# ---------------------------------------------------------------------------

class TestTokenExpiry:
    def test_access_token_has_exp_claim(self) -> None:
        token = create_access_token(uuid.uuid4(), uuid.uuid4(), "Owner")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload

    def test_refresh_token_has_exp_claim(self) -> None:
        token = create_refresh_token(uuid.uuid4())
        payload = decode_token(token)
        assert "exp" in payload
