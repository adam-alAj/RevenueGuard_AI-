"""Known-answer fixture data for the 6 MVP rules.

Every monetary value is exact — tests assert against these exact numbers,
not "found something." This is what makes the rules engine trustworthy.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Shared IDs
# ---------------------------------------------------------------------------
ORG_ID = _uuid()
CUSTOMER_A = _uuid()
CUSTOMER_B = _uuid()
CONTRACT_A = _uuid()  # $10,000 contract for Customer A
CONTRACT_B = _uuid()  # $5,000 contract for Customer B
PROJECT_1 = _uuid()  # Completed project under Contract A
PROJECT_2 = _uuid()  # Active project under Contract B
PROJECT_3 = _uuid()  # Completed project, NO contract
INVOICE_1 = _uuid()  # $8,000 invoice for Contract A (underbilling by $2,000)
INVOICE_2 = _uuid()  # $5,000 invoice for Contract B (full billing)
INVOICE_3 = _uuid()  # Overdue invoice, $3,000 outstanding
PAYMENT_1 = _uuid()  # $4,000 payment for Customer A
PAYMENT_2 = _uuid()  # $5,000 payment for Customer B (covers INVOICE_2)
RULE_VERSION_ID = _uuid()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECTS = [
    {
        "id": PROJECT_1,
        "name": "Website Redesign",
        "status": "completed",
        "customer_id": CUSTOMER_A,
        "contract_id": CONTRACT_A,
        "is_billable": True,
        "end_date": date(2026, 1, 15),
        "start_date": date(2025, 10, 1),
    },
    {
        "id": PROJECT_2,
        "name": "Monthly Support",
        "status": "active",
        "customer_id": CUSTOMER_B,
        "contract_id": CONTRACT_B,
        "is_billable": True,
        "end_date": None,
        "start_date": date(2026, 1, 1),
    },
    {
        "id": PROJECT_3,
        "name": "Internal Tool",
        "status": "completed",
        "customer_id": CUSTOMER_A,
        "contract_id": None,
        "is_billable": True,
        "end_date": date(2025, 12, 1),
        "start_date": date(2025, 6, 1),
    },
]

CONTRACTS = [
    {
        "id": CONTRACT_A,
        "name": "Website Contract",
        "customer_id": CUSTOMER_A,
        "start_date": date(2025, 10, 1),
        "end_date": date(2026, 3, 31),
        "expiration_date": date(2026, 3, 31),
        "total_value": Decimal("10000"),
        "billing_frequency": "project",
    },
    {
        "id": CONTRACT_B,
        "name": "Support Contract",
        "customer_id": CUSTOMER_B,
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
        "expiration_date": date(2026, 12, 31),
        "total_value": Decimal("5000"),
        "billing_frequency": "monthly",
    },
]

CONTRACT_LINES = [
    # Contract A: 2 lines totaling $10,000
    {
        "id": _uuid(),
        "contract_id": CONTRACT_A,
        "description": "Design",
        "quantity": 100,
        "unit_price": Decimal("50"),
        "total": Decimal("5000"),
    },
    {
        "id": _uuid(),
        "contract_id": CONTRACT_A,
        "description": "Development",
        "quantity": 100,
        "unit_price": Decimal("50"),
        "total": Decimal("5000"),
    },
    # Contract B: 1 line totaling $5,000
    {
        "id": _uuid(),
        "contract_id": CONTRACT_B,
        "description": "Support Hours",
        "quantity": 100,
        "unit_price": Decimal("50"),
        "total": Decimal("5000"),
    },
]

INVOICES = [
    # INVOICE_1: Underbilling — $8,000 vs $10,000 contract (missing $2,000)
    {
        "id": INVOICE_1,
        "invoice_number": "INV-001",
        "customer_id": CUSTOMER_A,
        "contract_id": CONTRACT_A,
        "project_id": PROJECT_1,
        "total": Decimal("8000"),
        "outstanding_balance": Decimal("0"),
        "due_date": date(2026, 2, 15),
        "issued_date": date(2026, 1, 15),
    },
    # INVOICE_2: Full billing — $5,000 matches contract
    {
        "id": INVOICE_2,
        "invoice_number": "INV-002",
        "customer_id": CUSTOMER_B,
        "contract_id": CONTRACT_B,
        "project_id": PROJECT_2,
        "total": Decimal("5000"),
        "outstanding_balance": Decimal("0"),
        "due_date": date(2026, 2, 1),
        "issued_date": date(2026, 1, 1),
    },
    # INVOICE_3: Overdue — $3,000 outstanding, past due
    {
        "id": INVOICE_3,
        "invoice_number": "INV-003",
        "customer_id": CUSTOMER_A,
        "contract_id": CONTRACT_A,
        "project_id": None,
        "total": Decimal("3000"),
        "outstanding_balance": Decimal("3000"),
        "due_date": date(2026, 1, 1),
        "issued_date": date(2025, 12, 1),
    },
]

INVOICE_LINES = [
    # Invoice 1: $8,000 total (underbilling — contract was $10,000)
    {
        "id": _uuid(),
        "invoice_id": INVOICE_1,
        "description": "Design",
        "quantity": 100,
        "unit_price": Decimal("40"),
        "total": Decimal("4000"),  # $40 vs $50 contract
    },
    {
        "id": _uuid(),
        "invoice_id": INVOICE_1,
        "description": "Development",
        "quantity": 100,
        "unit_price": Decimal("40"),
        "total": Decimal("4000"),  # $40 vs $50 contract
    },
    # Invoice 2: $5,000 (matches contract)
    {
        "id": _uuid(),
        "invoice_id": INVOICE_2,
        "description": "Support Hours",
        "quantity": 100,
        "unit_price": Decimal("50"),
        "total": Decimal("5000"),
    },
    # Invoice 3: $3,000 (standalone, overdue)
    {
        "id": _uuid(),
        "invoice_id": INVOICE_3,
        "description": "Consulting",
        "quantity": 40,
        "unit_price": Decimal("75"),
        "total": Decimal("3000"),
    },
]

PAYMENTS = [
    # Payment 1: $4,000 from Customer A
    {
        "id": PAYMENT_1,
        "customer_id": CUSTOMER_A,
        "amount": Decimal("4000"),
        "payment_date": date(2026, 1, 20),
    },
    # Payment 2: $5,000 from Customer B (covers Invoice 2)
    {
        "id": PAYMENT_2,
        "customer_id": CUSTOMER_B,
        "amount": Decimal("5000"),
        "payment_date": date(2026, 1, 10),
    },
]

CREDIT_NOTES = []  # No credit notes in the default fixture


# ---------------------------------------------------------------------------
# Composite fixture for the full engine test
# ---------------------------------------------------------------------------


def get_full_context(today: date | None = None) -> dict:
    """Return a complete RuleContext-compatible dict for testing."""

    return {
        "organization_id": ORG_ID,
        "rule_version_id": RULE_VERSION_ID,
        "parameters": {},
        "today": today or date(2026, 6, 15),
        "projects": PROJECTS,
        "contracts": CONTRACTS,
        "contract_lines": CONTRACT_LINES,
        "invoices": INVOICES,
        "invoice_lines": INVOICE_LINES,
        "payments": PAYMENTS,
        "credit_notes": CREDIT_NOTES,
    }
