"""Payment API endpoints — list with pagination and RBAC.

Endpoints:
- GET /api/v1/payments — List payments (paginated, filterable)
- GET /api/v1/payments/{id} — Get payment by ID
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.pagination import PaginationParams, paginate
from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentResponse(BaseModel):
    """Response for a payment."""

    id: str
    organization_id: str
    customer_id: str
    amount: str
    currency: str = "USD"
    payment_date: str
    payment_method: str | None = None
    reference: str | None = None


class PaymentListResponse(BaseModel):
    """Paginated list of payments."""

    items: list[PaymentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


_payment_store: dict[str, dict] = {}


@router.get("", response_model=PaymentListResponse)
async def list_payments(
    pagination: PaginationParams = Depends(),
    customer_id: str | None = Query(None, description="Filter by customer"),
    search: str | None = Query(None, description="Search by reference"),
    user: Any = Depends(require_permission("payments", "read")),
) -> PaymentListResponse:
    """List payments with pagination and filters."""
    org_id = str(user.organization_id)
    payments = [p for p in _payment_store.values() if p.get("organization_id") == org_id]

    if customer_id:
        payments = [p for p in payments if p.get("customer_id") == customer_id]
    if search:
        search_lower = search.lower()
        payments = [p for p in payments if search_lower in (p.get("reference") or "").lower()]

    total = len(payments)
    payments.sort(key=lambda x: x.get("payment_date", ""), reverse=True)
    start = pagination.offset
    page_items = payments[start : start + pagination.page_size]

    return PaymentListResponse(**paginate(page_items, total, pagination.page, pagination.page_size))


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    user: Any = Depends(require_permission("payments", "read")),
) -> PaymentResponse:
    """Get a payment by ID."""
    payment = _payment_store.get(payment_id)
    if not payment or payment.get("organization_id") != str(user.organization_id):
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentResponse(**payment)
