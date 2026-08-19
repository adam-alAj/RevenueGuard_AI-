"""Read-only investigation tools for leakage case analysis.

Every tool is:
- Tenant-scoped (organization_id injected from context, never from LLM)
- Audited through the Phase 7 scaffold
- Read-only (no mutations)
"""

from __future__ import annotations

from typing import Any

from app.agents.tools.base import create_tenant_scoped_tool

# In-memory data store for tools (will be replaced with DB queries in production)
# For tests, this is populated by the test fixtures
_data_store: dict[str, dict[str, list[dict[str, Any]]]] = {}


def set_data_store(store: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
    """Set the data store (for testing)."""
    global _data_store
    _data_store = store


def clear_data_store() -> None:
    """Clear the data store."""
    global _data_store
    _data_store = {}


def _get_org_data(org_id: str) -> dict[str, list[dict[str, Any]]]:
    """Get data for an organization."""
    return _data_store.get(org_id, {})


def _filter_by_org(items: list[dict[str, Any]], org_id: str) -> list[dict[str, Any]]:
    """Filter items by organization_id."""
    return [item for item in items if str(item.get("organization_id")) == org_id]


# --- Tool implementations ---


async def get_customer(organization_id: str, customer_id: str) -> dict[str, Any] | None:
    """Get a customer by ID, scoped to the organization."""
    org_data = _get_org_data(organization_id)
    customers = org_data.get("customers", [])
    for c in customers:
        if str(c["id"]) == customer_id and str(c.get("organization_id")) == organization_id:
            return c
    return None


async def get_contract(organization_id: str, contract_id: str) -> dict[str, Any] | None:
    """Get a contract by ID, scoped to the organization."""
    org_data = _get_org_data(organization_id)
    contracts = org_data.get("contracts", [])
    for c in contracts:
        if str(c["id"]) == contract_id and str(c.get("organization_id")) == organization_id:
            return c
    return None


async def get_contract_lines(organization_id: str, contract_id: str) -> list[dict[str, Any]]:
    """Get all line items for a contract, scoped to the organization."""
    org_data = _get_org_data(organization_id)
    lines = org_data.get("contract_lines", [])
    return [
        line
        for line in lines
        if str(line.get("contract_id")) == contract_id
        and str(line.get("organization_id")) == organization_id
    ]


async def get_invoice(organization_id: str, invoice_id: str) -> dict[str, Any] | None:
    """Get an invoice by ID, scoped to the organization."""
    org_data = _get_org_data(organization_id)
    invoices = org_data.get("invoices", [])
    for inv in invoices:
        if str(inv["id"]) == invoice_id and str(inv.get("organization_id")) == organization_id:
            return inv
    return None


async def get_invoice_lines(organization_id: str, invoice_id: str) -> list[dict[str, Any]]:
    """Get all line items for an invoice, scoped to the organization."""
    org_data = _get_org_data(organization_id)
    lines = org_data.get("invoice_lines", [])
    return [
        line
        for line in lines
        if str(line.get("invoice_id")) == invoice_id
        and str(line.get("organization_id")) == organization_id
    ]


async def get_payments(organization_id: str, invoice_id: str) -> list[dict[str, Any]]:
    """Get all payments for an invoice, scoped to the organization."""
    org_data = _get_org_data(organization_id)
    payments = org_data.get("payments", [])
    return [
        p
        for p in payments
        if str(p.get("invoice_id")) == invoice_id
        and str(p.get("organization_id")) == organization_id
    ]


async def get_project(organization_id: str, project_id: str) -> dict[str, Any] | None:
    """Get a project by ID, scoped to the organization."""
    org_data = _get_org_data(organization_id)
    projects = org_data.get("projects", [])
    for proj in projects:
        if str(proj["id"]) == project_id and str(proj.get("organization_id")) == organization_id:
            return proj
    return None


async def search_customer_history(organization_id: str, customer_id: str) -> list[dict[str, Any]]:
    """Search for all historical records related to a customer, scoped to org."""
    org_data = _get_org_data(organization_id)
    results = []

    # Find all contracts for this customer
    contracts = org_data.get("contracts", [])
    for c in contracts:
        if (
            str(c.get("customer_id")) == customer_id
            and str(c.get("organization_id")) == organization_id
        ):
            results.append({"type": "contract", "data": c})

    # Find all invoices for this customer
    invoices = org_data.get("invoices", [])
    for inv in invoices:
        if (
            str(inv.get("customer_id")) == customer_id
            and str(inv.get("organization_id")) == organization_id
        ):
            results.append({"type": "invoice", "data": inv})

    # Find all payments for this customer
    payments = org_data.get("payments", [])
    for p in payments:
        if (
            str(p.get("customer_id")) == customer_id
            and str(p.get("organization_id")) == organization_id
        ):
            results.append({"type": "payment", "data": p})

    return results


async def search_credit_notes(organization_id: str, customer_id: str) -> list[dict[str, Any]]:
    """Search for credit notes related to a customer, scoped to org."""
    org_data = _get_org_data(organization_id)
    credit_notes = org_data.get("credit_notes", [])
    return _filter_by_org(
        [cn for cn in credit_notes if str(cn.get("customer_id")) == customer_id],
        organization_id,
    )


async def search_contract_amendments(
    organization_id: str, contract_id: str
) -> list[dict[str, Any]]:
    """Search for amendments to a contract, scoped to org.

    Amendments are stored as contracts with a parent_contract_id.
    """
    org_data = _get_org_data(organization_id)
    contracts = org_data.get("contracts", [])
    return [
        c
        for c in contracts
        if str(c.get("parent_contract_id")) == contract_id
        and str(c.get("organization_id")) == organization_id
    ]


# --- Create tool instances using the scaffold ---

get_customer_tool = create_tenant_scoped_tool(
    name="get_customer",
    description="Get a customer by ID. Returns customer details including name, email, and status.",
    func=get_customer,
)

get_contract_tool = create_tenant_scoped_tool(
    name="get_contract",
    description="Get a contract by ID. Returns contract terms, dates, and status.",
    func=get_contract,
)

get_contract_lines_tool = create_tenant_scoped_tool(
    name="get_contract_lines",
    description="Get all line items for a contract. Returns pricing, quantities, and descriptions.",
    func=get_contract_lines,
)

get_invoice_tool = create_tenant_scoped_tool(
    name="get_invoice",
    description="Get an invoice by ID. Returns invoice details including total, status, and dates.",
    func=get_invoice,
)

get_invoice_lines_tool = create_tenant_scoped_tool(
    name="get_invoice_lines",
    description="Get all line items for an invoice. Returns pricing, quantities, and descriptions.",
    func=get_invoice_lines,
)

get_payments_tool = create_tenant_scoped_tool(
    name="get_payments",
    description="Get all payments for an invoice. Returns payment amounts, dates, and methods.",
    func=get_payments,
)

get_project_tool = create_tenant_scoped_tool(
    name="get_project",
    description="Get a project by ID. Returns project details including status and dates.",
    func=get_project,
)

search_customer_history_tool = create_tenant_scoped_tool(
    name="search_customer_history",
    description="Search all historical records for a customer (contracts, invoices, payments).",
    func=search_customer_history,
)

search_credit_notes_tool = create_tenant_scoped_tool(
    name="search_credit_notes",
    description="Search for credit notes related to a customer.",
    func=search_credit_notes,
)

search_contract_amendments_tool = create_tenant_scoped_tool(
    name="search_contract_amendments",
    description="Search for amendments to a contract. Returns any modified terms or addenda.",
    func=search_contract_amendments,
)


# All investigation tools as a list for agent construction
INVESTIGATION_TOOLS = [
    get_customer_tool,
    get_contract_tool,
    get_contract_lines_tool,
    get_invoice_tool,
    get_invoice_lines_tool,
    get_payments_tool,
    get_project_tool,
    search_customer_history_tool,
    search_credit_notes_tool,
    search_contract_amendments_tool,
]
