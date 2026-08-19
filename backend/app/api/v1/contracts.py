"""Contract API endpoints — CRUD with pagination and RBAC.

Endpoints:
- GET /api/v1/contracts — List contracts (paginated, filterable)
- GET /api/v1/contracts/{id} — Get contract by ID
- POST /api/v1/contracts — Create contract
- PATCH /api/v1/contracts/{id} — Update contract
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.v1.pagination import PaginationParams, paginate
from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["contracts"])


class ContractCreate(BaseModel):
    """Request body for creating a contract."""

    customer_id: str = Field(description="Customer ID")
    name: str = Field(description="Contract name/number")
    external_id: str | None = Field(default=None, description="External system ID")
    start_date: str | None = Field(default=None, description="Contract start date")
    end_date: str | None = Field(default=None, description="Contract end date")
    status: str = Field(default="active", description="Contract status")


class ContractUpdate(BaseModel):
    """Request body for updating a contract."""

    name: str | None = None
    status: str | None = None
    end_date: str | None = None


class ContractResponse(BaseModel):
    """Response for a contract."""

    id: str
    organization_id: str
    customer_id: str
    name: str
    external_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str = "active"


class ContractListResponse(BaseModel):
    """Paginated list of contracts."""

    items: list[ContractResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


_contract_store: dict[str, dict] = {}


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    pagination: PaginationParams = Depends(),
    customer_id: str | None = Query(None, description="Filter by customer"),
    status: str | None = Query(None, description="Filter by status"),
    search: str | None = Query(None, description="Search by name"),
    user: Any = Depends(require_permission("contracts", "read")),
) -> ContractListResponse:
    """List contracts with pagination and filters."""
    org_id = str(user.organization_id)
    contracts = [c for c in _contract_store.values() if c.get("organization_id") == org_id]

    if customer_id:
        contracts = [c for c in contracts if c.get("customer_id") == customer_id]
    if status:
        contracts = [c for c in contracts if c.get("status") == status]
    if search:
        search_lower = search.lower()
        contracts = [c for c in contracts if search_lower in c.get("name", "").lower()]

    total = len(contracts)
    contracts.sort(key=lambda x: x.get("name", ""))
    start = pagination.offset
    page_items = contracts[start : start + pagination.page_size]

    return ContractListResponse(**paginate(page_items, total, pagination.page, pagination.page_size))


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    user: Any = Depends(require_permission("contracts", "read")),
) -> ContractResponse:
    """Get a contract by ID."""
    contract = _contract_store.get(contract_id)
    if not contract or contract.get("organization_id") != str(user.organization_id):
        raise HTTPException(status_code=404, detail="Contract not found")
    return ContractResponse(**contract)


@router.post("", response_model=ContractResponse, status_code=201)
async def create_contract(
    request: ContractCreate,
    user: Any = Depends(require_permission("contracts", "write")),
) -> ContractResponse:
    """Create a new contract."""
    contract_id = str(uuid.uuid4())
    contract = {
        "id": contract_id,
        "organization_id": str(user.organization_id),
        "customer_id": request.customer_id,
        "name": request.name,
        "external_id": request.external_id,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "status": request.status,
    }
    _contract_store[contract_id] = contract
    return ContractResponse(**contract)


@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: str,
    request: ContractUpdate,
    user: Any = Depends(require_permission("contracts", "write")),
) -> ContractResponse:
    """Update a contract."""
    contract = _contract_store.get(contract_id)
    if not contract or contract.get("organization_id") != str(user.organization_id):
        raise HTTPException(status_code=404, detail="Contract not found")
    update_data = request.model_dump(exclude_unset=True)
    contract.update(update_data)
    return ContractResponse(**contract)
