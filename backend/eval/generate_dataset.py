"""Seeded synthetic dataset generator for evaluation.

Creates deterministic, reproducible in-memory datasets that feed directly
into the rule engine's RuleContext without touching the database.

Scale: ~200 customers, ~50 contracts, ~500 invoices, ~500 payments, ~50 projects.
All IDs are deterministic UUIDs derived from the seed for reproducibility.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

SEED = 42
EVAL_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
EVAL_ORG_NAME = "Evaluation Tenant (Synthetic)"


def _deterministic_uuid(seed_str: str) -> uuid.UUID:
    """Generate a deterministic UUID from a seed string."""
    h = hashlib.sha256(seed_str.encode()).hexdigest()
    return uuid.UUID(h[:32])


def _make_id(prefix: str, index: int) -> uuid.UUID:
    """Create a deterministic UUID for an entity."""
    return _deterministic_uuid(f"{SEED}:{prefix}:{index}")


@dataclass
class GeneratedDataset:
    """Complete generated dataset for evaluation."""

    customers: list[dict[str, Any]]
    contracts: list[dict[str, Any]]
    contract_lines: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    invoice_lines: list[dict[str, Any]]
    payments: list[dict[str, Any]]
    credit_notes: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    today: date


def generate_dataset(today: date | None = None) -> GeneratedDataset:
    """Generate a complete seeded dataset.

    The dataset contains:
    - 200 customers
    - 50 contracts (various states: active, expired, with renewals)
    - 500 invoices (including deliberately incomplete ones)
    - 500 payments (including partial payments)
    - 50 projects (including completed projects without invoices)
    """
    if today is None:
        today = date(2025, 7, 15)

    customers = _generate_customers(200)
    contracts, contract_lines = _generate_contracts(customers, 50)
    projects = _generate_projects(customers, contracts, 50)
    invoices, invoice_lines = _generate_invoices(customers, contracts, projects, 500)
    payments = _generate_payments(customers, invoices, 500)
    credit_notes = _generate_credit_notes(invoices, 20)

    return GeneratedDataset(
        customers=customers,
        contracts=contracts,
        contract_lines=contract_lines,
        invoices=invoices,
        invoice_lines=invoice_lines,
        payments=payments,
        credit_notes=credit_notes,
        projects=projects,
        today=today,
    )


def _generate_customers(count: int) -> list[dict[str, Any]]:
    """Generate customers with deterministic data."""
    customers = []
    industries = [
        "Technology", "Finance", "Healthcare", "Manufacturing",
        "Retail", "Energy", "Consulting", "Legal", "Media", "Education",
    ]
    for i in range(count):
        customers.append({
            "id": _make_id("cust", i),
            "name": f"Eval Customer {i:04d}",
            "external_id": f"EVAL-CUST-{i:04d}",
            "organization_id": EVAL_ORG_ID,
            "industry": industries[i % len(industries)],
        })
    return customers


def _generate_contracts(
    customers: list[dict[str, Any]],
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate contracts and contract lines."""
    contracts = []
    contract_lines = []
    billing_freqs = ["monthly", "quarterly", "annually"]

    for i in range(count):
        customer = customers[i % len(customers)]
        cid = _make_id("contract", i)

        # Determine contract state
        is_expired = i % 5 == 0  # 20% expired
        has_renewal = i % 7 == 0  # ~14% have renewals (some overlap with expired)
        monthly_value = Decimal(str(1000 + (i * 200) % 10000))

        start = date(2025, 1, 1) + timedelta(days=(i * 7) % 180)
        end = start + timedelta(days=365) if is_expired else start + timedelta(days=730)

        expiration = end
        billing_freq = billing_freqs[i % 3]

        line_count = 1 + (i % 3)
        total_value = Decimal("0")
        for j in range(line_count):
            qty = 1 + (j % 5)
            unit_price = monthly_value / line_count
            line_total = Decimal(str(qty)) * unit_price
            total_value += line_total

            contract_lines.append({
                "id": _make_id("cline", i * 10 + j),
                "contract_id": cid,
                "description": f"Line item {j + 1}",
                "quantity": qty,
                "unit_price": unit_price,
                "total": line_total,
            })

        contracts.append({
            "id": cid,
            "name": f"Contract {i:04d} - {customer['name']}",
            "customer_id": customer["id"],
            "organization_id": EVAL_ORG_ID,
            "start_date": start,
            "end_date": end,
            "expiration_date": expiration,
            "total_value": total_value,
            "billing_frequency": billing_freq,
            "parent_contract_id": _make_id("contract", i - 1) if has_renewal and i > 0 else None,
        })

    return contracts, contract_lines


def _generate_projects(
    customers: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    count: int,
) -> list[dict[str, Any]]:
    """Generate projects — some completed without invoices (missing invoice cases)."""
    projects = []
    for i in range(count):
        customer = customers[i % len(customers)]
        contract = contracts[i % len(contracts)]
        is_completed = i % 3 == 0  # ~33% completed
        is_billable = i % 10 != 9  # 90% billable

        end = date(2025, 6, 1) + timedelta(days=(i * 5) % 60)

        projects.append({
            "id": _make_id("project", i),
            "name": f"Project {i:04d}",
            "status": "completed" if is_completed else "active",
            "customer_id": customer["id"],
            "contract_id": contract["id"],
            "is_billable": is_billable,
            "start_date": end - timedelta(days=90),
            "end_date": end,
        })
    return projects


def _generate_invoices(
    customers: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate invoices — some deliberately incomplete or overdue."""
    invoices = []
    invoice_lines = []

    for i in range(count):
        customer = customers[i % len(customers)]
        contract = contracts[i % len(contracts)]
        project = projects[i % len(projects)]

        inv_id = _make_id("inv", i)
        is_overdue = i % 8 == 0  # ~12% overdue
        is_partial = i % 10 == 0  # 10% partial payment

        total = Decimal(str(500 + (i * 150) % 8000))
        if is_overdue:
            outstanding = total  # Fully outstanding
        elif is_partial:
            outstanding = total * Decimal("0.3")  # 30% outstanding
        else:
            outstanding = Decimal("0")

        due = date(2025, 6, 1) + timedelta(days=(i * 3) % 60)
        issued = due - timedelta(days=30)

        invoices.append({
            "id": inv_id,
            "invoice_number": f"INV-EVAL-{i:05d}",
            "customer_id": customer["id"],
            "contract_id": contract["id"],
            "project_id": project["id"],
            "organization_id": EVAL_ORG_ID,
            "total": total,
            "outstanding_balance": outstanding,
            "due_date": due,
            "issued_date": issued,
        })

        # Add invoice line items
        invoice_lines.append({
            "id": _make_id("iline", i),
            "invoice_id": inv_id,
            "description": f"Invoice line for {i:05d}",
            "quantity": 1,
            "unit_price": total,
            "total": total,
        })

    return invoices, invoice_lines


def _generate_payments(
    customers: list[dict[str, Any]],
    invoices: list[dict[str, Any]],
    count: int,
) -> list[dict[str, Any]]:
    """Generate payments — some partial, some matching invoices exactly."""
    payments = []
    for i in range(count):
        customer = customers[i % len(customers)]
        invoice = invoices[i % len(invoices)]

        # Most payments cover the invoice; some are partial
        is_partial = i % 12 == 0
        inv_total = Decimal(str(invoice["total"]))
        amount = inv_total * Decimal("0.5") if is_partial else inv_total

        payments.append({
            "id": _make_id("pay", i),
            "customer_id": customer["id"],
            "invoice_id": invoice["id"],
            "amount": amount,
            "payment_date": invoice.get("due_date", date(2025, 7, 1)),
            "organization_id": EVAL_ORG_ID,
        })
    return payments


def _generate_credit_notes(
    invoices: list[dict[str, Any]],
    count: int,
) -> list[dict[str, Any]]:
    """Generate credit notes for some invoices."""
    credit_notes = []
    for i in range(count):
        invoice = invoices[i % len(invoices)]
        inv_total = Decimal(str(invoice["total"]))
        credit_notes.append({
            "id": _make_id("cn", i),
            "invoice_id": invoice["id"],
            "amount": inv_total * Decimal("0.1"),  # 10% credit
            "customer_id": invoice["customer_id"],
            "organization_id": EVAL_ORG_ID,
        })
    return credit_notes
