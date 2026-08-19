"""Invoice API endpoints — list with pagination and RBAC.

Endpoints:
- GET /api/v1/invoices — List invoices (paginated, filterable)
- GET /api/v1/invoices/{id} — Get invoice by ID
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.pagination import PaginationParams, paginate
from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])


class InvoiceResponse(BaseModel):
    """Response for an invoice."""

    id: str
    organization_id: str
    customer_id: str
    contract_id: str | None = None
    invoice_number: str
    total: str
    outstanding_balance: str
    status: str
    currency: str = "USD"


class InvoiceListResponse(BaseModel):
    """Paginated list of invoices."""

    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


_invoice_store: dict[str, dict] = {}


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    pagination: PaginationParams = Depends(),
    customer_id: str | None = Query(None, description="Filter by customer"),
    status: str | None = Query(None, description="Filter by status"),
    search: str | None = Query(None, description="Search by invoice number"),
    user: Any = Depends(require_permission("invoices", "read")),
) -> InvoiceListResponse:
    """List invoices with pagination and filters."""
    org_id = str(user.organization_id)
    invoices = [i for i in _invoice_store.values() if i.get("organization_id") == org_id]

    if customer_id:
        invoices = [i for i in invoices if i.get("customer_id") == customer_id]
    if status:
        invoices = [i for i in invoices if i.get("status") == status]
    if search:
        search_lower = search.lower()
        invoices = [i for i in invoices if search_lower in i.get("invoice_number", "").lower()]

    total = len(invoices)
    invoices.sort(key=lambda x: x.get("invoice_number", ""))
    start = pagination.offset
    page_items = invoices[start : start + pagination.page_size]

    return InvoiceListResponse(
        **paginate(page_items, total, pagination.page, pagination.page_size)
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    user: Any = Depends(require_permission("invoices", "read")),
) -> InvoiceResponse:
    """Get an invoice by ID."""
    invoice = _invoice_store.get(invoice_id)
    if not invoice or invoice.get("organization_id") != str(user.organization_id):
        raise HTTPException(status_code=404, detail="Invoice not found")
    return InvoiceResponse(**invoice)
