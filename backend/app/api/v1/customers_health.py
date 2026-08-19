"""Customer revenue-health API — aggregation endpoint.

Endpoints:
- GET /api/v1/customers/{id}/revenue-health — Aggregated revenue metrics
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers-health"])


class RevenueHealthResponse(BaseModel):
    """Aggregated revenue health for a customer."""

    customer_id: str
    customer_name: str
    total_contract_value: str
    total_invoiced: str
    total_paid: str
    total_outstanding: str
    potential_leakage: str
    recovered_amount: str
    active_subscriptions: int
    open_cases: int


# In-memory stores for aggregation
_health_customer_store: dict[str, dict] = {}
_health_contract_store: dict[str, dict] = {}
_health_invoice_store: dict[str, dict] = {}
_health_payment_store: dict[str, dict] = {}
_health_case_store: dict[str, dict] = {}
_health_subscription_store: dict[str, dict] = {}


def set_health_data(
    customers: dict[str, dict] | None = None,
    contracts: dict[str, dict] | None = None,
    invoices: dict[str, dict] | None = None,
    payments: dict[str, dict] | None = None,
    cases: dict[str, dict] | None = None,
    subscriptions: dict[str, dict] | None = None,
) -> None:
    """Set data stores for testing."""
    global _health_customer_store, _health_contract_store
    global _health_invoice_store, _health_payment_store
    global _health_case_store, _health_subscription_store
    if customers is not None:
        _health_customer_store = customers
    if contracts is not None:
        _health_contract_store = contracts
    if invoices is not None:
        _health_invoice_store = invoices
    if payments is not None:
        _health_payment_store = payments
    if cases is not None:
        _health_case_store = cases
    if subscriptions is not None:
        _health_subscription_store = subscriptions


def clear_health_data() -> None:
    """Clear all health data stores."""
    global _health_customer_store, _health_contract_store
    global _health_invoice_store, _health_payment_store
    global _health_case_store, _health_subscription_store
    _health_customer_store = {}
    _health_contract_store = {}
    _health_invoice_store = {}
    _health_payment_store = {}
    _health_case_store = {}
    _health_subscription_store = {}


@router.get("/{customer_id}/revenue-health", response_model=RevenueHealthResponse)
async def get_revenue_health(
    customer_id: str,
    user: Any = Depends(require_permission("customers", "read")),
) -> RevenueHealthResponse:
    """Get aggregated revenue health for a customer.

    Aggregates:
    - Total contract value
    - Total invoiced amount
    - Total paid amount
    - Total outstanding amount
    - Potential leakage across cases
    - Recovered amount
    - Active subscription count
    - Open case count
    """
    org_id = str(user.organization_id)

    # Get customer
    customer = _health_customer_store.get(customer_id)
    if not customer or customer.get("organization_id") != org_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Aggregate contract value
    total_contract = Decimal("0")
    for ct in _health_contract_store.values():
        if ct.get("customer_id") == customer_id and ct.get("organization_id") == org_id:
            # Sum contract line items if available
            total_contract += Decimal(str(ct.get("total_value", 0)))

    # Aggregate invoice amounts
    total_invoiced = Decimal("0")
    total_outstanding = Decimal("0")
    for inv in _health_invoice_store.values():
        if inv.get("customer_id") == customer_id and inv.get("organization_id") == org_id:
            total_invoiced += Decimal(str(inv.get("total", 0)))
            total_outstanding += Decimal(str(inv.get("outstanding_balance", 0)))

    # Aggregate payments
    total_paid = Decimal("0")
    for pay in _health_payment_store.values():
        if pay.get("customer_id") == customer_id and pay.get("organization_id") == org_id:
            total_paid += Decimal(str(pay.get("amount", 0)))

    # Aggregate cases
    potential_leakage = Decimal("0")
    recovered_amount = Decimal("0")
    open_cases = 0
    for case in _health_case_store.values():
        if case.get("customer_id") == customer_id and case.get("organization_id") == org_id:
            potential_leakage += Decimal(str(case.get("potential_leakage", 0)))
            recovered_amount += Decimal(str(case.get("recovered_amount", 0)))
            if case.get("status") not in ("closed", "recovered", "false_positive",
                                           "legitimate_exception", "rejected"):
                open_cases += 1

    # Count active subscriptions
    active_subs = 0
    for sub in _health_subscription_store.values():
        if (sub.get("customer_id") == customer_id
                and sub.get("organization_id") == org_id
                and sub.get("status") == "active"):
            active_subs += 1

    return RevenueHealthResponse(
        customer_id=customer_id,
        customer_name=customer.get("name", ""),
        total_contract_value=str(total_contract),
        total_invoiced=str(total_invoiced),
        total_paid=str(total_paid),
        total_outstanding=str(total_outstanding),
        potential_leakage=str(potential_leakage),
        recovered_amount=str(recovered_amount),
        active_subscriptions=active_subs,
        open_cases=open_cases,
    )
