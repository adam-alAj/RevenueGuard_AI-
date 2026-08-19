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

from fastapi.middleware.cors import CORSMiddleware

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


# ─── CORS (production-safe) ────────────────────────────────────────────────
settings = get_settings()
if settings.APP_ENV == "production":
    # Production: strict CORS — only allowed origins
    origins = [o.strip() for o in (settings.CORS_ORIGINS or "").split(",") if o.strip()]
    if not origins:
        origins = ["http://localhost"]  # Fallback for safety
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
else:
    # Development: permissive CORS for local frontend dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health", response_model=dict[str, str])
async def health_check() -> dict[str, str]:
    """Health check endpoint — returns 200 OK with status."""
    return {"status": "ok"}


# --- Register API routers ---
from app.api.v1.agents import router as agents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.contracts import router as contracts_router
from app.api.v1.customers import router as customers_router
from app.api.v1.customers_health import router as customers_health_router
from app.api.v1.entity_resolution import router as entity_resolution_router
from app.api.v1.imports import router as imports_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.leakage import router as leakage_router
from app.api.v1.leakage_approval import router as leakage_approval_router
from app.api.v1.leakage_inbox import router as leakage_inbox_router
from app.api.v1.observability import router as observability_router
from app.api.v1.payments import router as payments_router
from app.api.v1.recovery import router as recovery_router
from app.api.v1.rules import router as rules_router
from app.api.v1.search import router as search_router
from app.api.v1.users import router as users_router
from app.api.v1.verification import router as verification_router

API_PREFIX = "/api/v1"

for r in (
    auth_router,
    users_router,
    agents_router,
    imports_router,
    entity_resolution_router,
    rules_router,
    leakage_router,
    leakage_approval_router,
    leakage_inbox_router,
    recovery_router,
    verification_router,
    customers_router,
    contracts_router,
    invoices_router,
    payments_router,
    search_router,
    customers_health_router,
    observability_router,
):
    app.include_router(r, prefix=API_PREFIX)
