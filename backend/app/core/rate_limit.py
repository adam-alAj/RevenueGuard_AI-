"""Rate limiting middleware for security-sensitive endpoints.

Provides per-IP rate limiting for authentication endpoints to prevent
brute-force attacks. Uses an in-memory sliding-window counter (MVP —
replace with Redis in production).

Limits:
- Login: 10 attempts per 5 minutes per IP
- Register: 5 attempts per 10 minutes per IP
- Password reset: 3 attempts per 15 minutes per IP
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Sliding-window rate limiter using in-memory storage."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Store: {key: [timestamp, ...]}
        self._store: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str) -> None:
        """Remove expired entries."""
        now = time.time()
        cutoff = now - self.window_seconds
        self._store[key] = [t for t in self._store[key] if t > cutoff]

    def check(self, key: str) -> None:
        """Check rate limit. Raises 429 if exceeded."""
        self._cleanup(key)
        if len(self._store[key]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {self.window_seconds} seconds.",
            )
        self._store[key].append(time.time())


# Pre-configured limiters for auth endpoints
_login_limiter = RateLimiter(max_requests=10, window_seconds=300)  # 10 per 5 min
_register_limiter = RateLimiter(max_requests=5, window_seconds=600)  # 5 per 10 min
_password_reset_limiter = RateLimiter(max_requests=3, window_seconds=900)  # 3 per 15 min


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def rate_limit_login(request: Request) -> None:
    """Rate limit login attempts — 10 per 5 minutes per IP."""
    ip = _get_client_ip(request)
    _login_limiter.check(f"login:{ip}")


async def rate_limit_register(request: Request) -> None:
    """Rate limit registration — 5 per 10 minutes per IP."""
    ip = _get_client_ip(request)
    _register_limiter.check(f"register:{ip}")


async def rate_limit_password_reset(request: Request) -> None:
    """Rate limit password reset — 3 per 15 minutes per IP."""
    ip = _get_client_ip(request)
    _password_reset_limiter.check(f"pwdreset:{ip}")
