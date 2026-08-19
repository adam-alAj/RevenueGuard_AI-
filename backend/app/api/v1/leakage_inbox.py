"""Leakage Inbox API — full listing with composable filters and pagination.

Endpoints:
- GET /api/v1/leakage/inbox — Filterable, sortable leakage case listing
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.v1.pagination import PaginationParams, paginate
from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leakage", tags=["leakage-inbox"])


class LeakageCaseResponse(BaseModel):
    """Response for a leakage case in the inbox."""

    case_id: str
    case_number: str
    leakage_type: str
    status: str
    severity: str | None = None
    customer_id: str | None = None
    potential_leakage: str | None = None
    confidence: str | None = None
    assigned_to: str | None = None
    created_at: str | None = None


class LeakageInboxResponse(BaseModel):
    """Paginated leakage inbox response."""

    items: list[LeakageCaseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    filters_applied: dict[str, Any]


# In-memory store for testing
_leakage_store: dict[str, dict] = {}


def set_leakage_store(store: dict[str, dict]) -> None:
    """Set the leakage store (for testing)."""
    global _leakage_store
    _leakage_store.clear()
    _leakage_store.update(store)


def clear_leakage_store() -> None:
    """Clear the leakage store."""
    _leakage_store.clear()


@router.get("/inbox", response_model=LeakageInboxResponse)
async def list_leakage_inbox(
    pagination: PaginationParams = Depends(),
    leakage_type: str | None = Query(None, description="Filter by leakage type"),
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    customer_id: str | None = Query(None, description="Filter by customer"),
    min_amount: float | None = Query(None, description="Min potential leakage"),
    max_amount: float | None = Query(None, description="Max potential leakage"),
    min_confidence: float | None = Query(None, ge=0, le=1, description="Min confidence"),
    max_confidence: float | None = Query(None, ge=0, le=1, description="Max confidence"),
    date_from: str | None = Query(None, description="Start date (ISO 8601)"),
    date_to: str | None = Query(None, description="End date (ISO 8601)"),
    assigned_to: str | None = Query(None, description="Filter by assigned user"),
    search: str | None = Query(None, description="Search case number/description"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    user: Any = Depends(require_permission("leakage", "read")),
) -> LeakageInboxResponse:
    """List leakage cases with composable filters.

    Supports: leakage_type, status, severity, customer_id, amount range,
    confidence range, date range, assigned_to, full-text search.
    All filters are composable (AND logic).
    """
    org_id = str(user.organization_id)
    cases = [c for c in _leakage_store.values() if c.get("organization_id") == org_id]

    filters_applied: dict[str, Any] = {}

    # Apply composable filters
    if leakage_type:
        cases = [c for c in cases if c.get("leakage_type") == leakage_type]
        filters_applied["leakage_type"] = leakage_type

    if status:
        cases = [c for c in cases if c.get("status") == status]
        filters_applied["status"] = status

    if severity:
        cases = [c for c in cases if c.get("severity") == severity]
        filters_applied["severity"] = severity

    if customer_id:
        cases = [c for c in cases if c.get("customer_id") == customer_id]
        filters_applied["customer_id"] = customer_id

    if min_amount is not None:
        cases = [
            c
            for c in cases
            if c.get("potential_leakage") is not None
            and float(c["potential_leakage"]) >= min_amount
        ]
        filters_applied["min_amount"] = min_amount

    if max_amount is not None:
        cases = [
            c
            for c in cases
            if c.get("potential_leakage") is not None
            and float(c["potential_leakage"]) <= max_amount
        ]
        filters_applied["max_amount"] = max_amount

    if min_confidence is not None:
        cases = [
            c
            for c in cases
            if c.get("confidence") is not None and float(c["confidence"]) >= min_confidence
        ]
        filters_applied["min_confidence"] = min_confidence

    if max_confidence is not None:
        cases = [
            c
            for c in cases
            if c.get("confidence") is not None and float(c["confidence"]) <= max_confidence
        ]
        filters_applied["max_confidence"] = max_confidence

    if date_from:
        cases = [c for c in cases if c.get("created_at") and c["created_at"] >= date_from]
        filters_applied["date_from"] = date_from

    if date_to:
        cases = [c for c in cases if c.get("created_at") and c["created_at"] <= date_to]
        filters_applied["date_to"] = date_to

    if assigned_to:
        cases = [c for c in cases if c.get("assigned_to") == assigned_to]
        filters_applied["assigned_to"] = assigned_to

    if search:
        search_lower = search.lower()
        cases = [
            c
            for c in cases
            if search_lower in c.get("case_number", "").lower()
            or search_lower in (c.get("description") or "").lower()
        ]
        filters_applied["search"] = search

    # Sort
    reverse = sort_order == "desc"
    cases.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

    # Paginate
    total = len(cases)
    start = pagination.offset
    page_items = cases[start : start + pagination.page_size]

    return LeakageInboxResponse(
        **paginate(page_items, total, pagination.page, pagination.page_size),
        filters_applied=filters_applied,
    )
