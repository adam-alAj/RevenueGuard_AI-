"""RevenueGuard AI — FastAPI application entry point.

This module creates the FastAPI app with a health check endpoint.
No business logic is included in Phase 1.

Settings are loaded lazily on first server request, not at import time,
so tests can collect modules without requiring all secrets in the environment.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Validate settings on server startup — fail fast if secrets are missing."""
    get_settings()
    yield


app = FastAPI(
    title="RevenueGuard AI",
    lifespan=lifespan,
)


@app.get("/health", response_model=dict[str, str])
async def health_check() -> dict[str, str]:
    """Health check endpoint — returns 200 OK with status."""
    return {"status": "ok"}
