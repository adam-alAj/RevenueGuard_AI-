"""Search API — cross-entity search across customers, contracts, invoices, cases.

Endpoints:
- GET /api/v1/search — Search across all entities
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.v1.pagination import PaginationParams, paginate
from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    """A single search result."""

    entity_type: str  # customer, contract, invoice, case
    entity_id: str
    title: str
    subtitle: str | None = None
    matched_field: str
    relevance_score: float = 1.0


class SearchResponse(BaseModel):
    """Search results with pagination."""

    items: list[SearchResult]
    total: int
    page: int
    page_size: int
    total_pages: int
    query: str


# Import stores from other modules
from app.api.v1.contracts import _contract_store
from app.api.v1.customers import _customer_store
from app.api.v1.invoices import _invoice_store
from app.api.v1.leakage_inbox import _leakage_store


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    pagination: PaginationParams = Depends(),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    user: Any = Depends(require_permission("search", "read")),
) -> SearchResponse:
    """Search across customers, contracts, invoices, and leakage cases.

    Supports ILIKE-style matching on:
    - Customer: name, email
    - Contract: name, customer_id
    - Invoice: invoice_number
    - Case: case_number, description
    """
    org_id = str(user.organization_id)
    query_lower = q.lower()
    results: list[SearchResult] = []

    # Search customers
    if not entity_type or entity_type == "customer":
        for c in _customer_store.values():
            if c.get("organization_id") != org_id:
                continue
            name = c.get("name", "").lower()
            email = (c.get("email") or "").lower()
            if query_lower in name:
                results.append(
                    SearchResult(
                        entity_type="customer",
                        entity_id=c["id"],
                        title=c["name"],
                        subtitle=c.get("email"),
                        matched_field="name",
                    )
                )
            elif query_lower in email:
                results.append(
                    SearchResult(
                        entity_type="customer",
                        entity_id=c["id"],
                        title=c["name"],
                        subtitle=c.get("email"),
                        matched_field="email",
                    )
                )

    # Search contracts
    if not entity_type or entity_type == "contract":
        for ct in _contract_store.values():
            if ct.get("organization_id") != org_id:
                continue
            name = ct.get("name", "").lower()
            if query_lower in name:
                # Find customer name
                cust = _customer_store.get(ct.get("customer_id"))
                cust_name = cust["name"] if cust else None
                results.append(
                    SearchResult(
                        entity_type="contract",
                        entity_id=ct["id"],
                        title=ct["name"],
                        subtitle=cust_name,
                        matched_field="name",
                    )
                )

    # Search invoices
    if not entity_type or entity_type == "invoice":
        for inv in _invoice_store.values():
            if inv.get("organization_id") != org_id:
                continue
            inv_num = inv.get("invoice_number", "").lower()
            if query_lower in inv_num:
                results.append(
                    SearchResult(
                        entity_type="invoice",
                        entity_id=inv["id"],
                        title=inv["invoice_number"],
                        subtitle=f"${inv.get('total', '0')}",
                        matched_field="invoice_number",
                    )
                )

    # Search cases
    if not entity_type or entity_type == "case":
        for case in _leakage_store.values():
            if case.get("organization_id") != org_id:
                continue
            case_num = case.get("case_number", "").lower()
            desc = (case.get("description") or "").lower()
            if query_lower in case_num:
                results.append(
                    SearchResult(
                        entity_type="case",
                        entity_id=case.get("case_id", ""),
                        title=case["case_number"],
                        subtitle=case.get("leakage_type"),
                        matched_field="case_number",
                    )
                )
            elif query_lower in desc:
                results.append(
                    SearchResult(
                        entity_type="case",
                        entity_id=case.get("case_id", ""),
                        title=case["case_number"],
                        subtitle=case.get("leakage_type"),
                        matched_field="description",
                    )
                )

    # Sort by relevance (exact match > contains)
    results.sort(key=lambda r: (query_lower not in r.title.lower(), r.title))

    total = len(results)
    start = pagination.offset
    page_items = results[start : start + pagination.page_size]

    return SearchResponse(
        **paginate(page_items, total, pagination.page, pagination.page_size),
        query=q,
    )
