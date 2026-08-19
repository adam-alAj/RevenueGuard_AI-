"""Customer API endpoints — CRUD with pagination and RBAC.

Endpoints:
- GET /api/v1/customers — List customers (paginated, filterable)
- GET /api/v1/customers/{id} — Get customer by ID
- POST /api/v1/customers — Create customer
- PATCH /api/v1/customers/{id} — Update customer
- DELETE /api/v1/customers/{id} — Delete customer (soft-delete)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.v1.pagination import PaginationParams, paginate
from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


# --- Schemas ---


class CustomerCreate(BaseModel):
    """Request body for creating a customer."""

    name: str = Field(description="Customer name")
    email: str | None = Field(default=None, description="Primary contact email")
    phone: str | None = Field(default=None, description="Primary contact phone")
    company: str | None = Field(default=None, description="Company name")
    external_id: str | None = Field(default=None, description="External system ID")


class CustomerUpdate(BaseModel):
    """Request body for updating a customer."""

    name: str | None = Field(default=None, description="Customer name")
    email: str | None = Field(default=None, description="Primary contact email")
    phone: str | None = Field(default=None, description="Primary contact phone")
    company: str | None = Field(default=None, description="Company name")


class CustomerResponse(BaseModel):
    """Response for a customer."""

    id: str
    organization_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    external_id: str | None = None
    is_active: bool = True


class CustomerListResponse(BaseModel):
    """Paginated list of customers."""

    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# --- In-memory store (DB-backed in production) ---
_customer_store: dict[str, dict] = {}


# --- Endpoints ---


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    pagination: PaginationParams = Depends(),
    search: str | None = Query(None, description="Search by name/email"),
    user: Any = Depends(require_permission("customers", "read")),
) -> CustomerListResponse:
    """List customers with pagination and optional search."""
    org_id = str(user.organization_id)

    # Filter by org
    customers = [c for c in _customer_store.values() if c.get("organization_id") == org_id]

    # Apply search filter
    if search:
        search_lower = search.lower()
        customers = [
            c for c in customers
            if search_lower in c.get("name", "").lower()
            or search_lower in (c.get("email") or "").lower()
        ]

    total = len(customers)
    # Sort by name
    customers.sort(key=lambda x: x.get("name", ""))
    # Paginate
    start = pagination.offset
    end = start + pagination.page_size
    page_items = customers[start:end]

    return CustomerListResponse(
        **paginate(page_items, total, pagination.page, pagination.page_size),
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    user: Any = Depends(require_permission("customers", "read")),
) -> CustomerResponse:
    """Get a customer by ID."""
    customer = _customer_store.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.get("organization_id") != str(user.organization_id):
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerResponse(**customer)


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    request: CustomerCreate,
    user: Any = Depends(require_permission("customers", "write")),
) -> CustomerResponse:
    """Create a new customer."""
    import uuid

    customer_id = str(uuid.uuid4())
    customer = {
        "id": customer_id,
        "organization_id": str(user.organization_id),
        "name": request.name,
        "email": request.email,
        "phone": request.phone,
        "company": request.company,
        "external_id": request.external_id,
        "is_active": True,
    }
    _customer_store[customer_id] = customer

    return CustomerResponse(**customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    request: CustomerUpdate,
    user: Any = Depends(require_permission("customers", "write")),
) -> CustomerResponse:
    """Update a customer."""
    customer = _customer_store.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.get("organization_id") != str(user.organization_id):
        raise HTTPException(status_code=404, detail="Customer not found")

    # Apply updates
    update_data = request.model_dump(exclude_unset=True)
    customer.update(update_data)

    return CustomerResponse(**customer)


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: str,
    user: Any = Depends(require_permission("customers", "delete")),
) -> None:
    """Soft-delete a customer."""
    customer = _customer_store.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.get("organization_id") != str(user.organization_id):
        raise HTTPException(status_code=404, detail="Customer not found")

    customer["is_active"] = False
