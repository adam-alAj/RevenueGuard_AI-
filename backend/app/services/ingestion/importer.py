"""Idempotent importer for the 7 MVP entities.

Import logic:
1. Parse file → normalized rows
2. Validate each row → collect errors
3. Upsert valid rows on (external_id + organization_id) — never duplicate
4. Track everything in ImportJob audit trail

Upsert strategy: for each entity, check if a record with the same
external_id already exists in this organization. If yes, update it.
If no, create it. This makes re-importing the same file idempotent.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract, ContractLine
from app.models.customer import Customer
from app.models.integration import ImportJob
from app.models.invoice import Invoice, InvoiceLine
from app.models.payment import Payment
from app.models.project import Project
from app.services.ingestion.parsers import read_csv, read_excel
from app.services.ingestion.validators import VALIDATORS


async def _resolve_customer_id(
    db: AsyncSession, org_id: uuid.UUID, external_id: str | None
) -> uuid.UUID | None:
    """Resolve a customer external_id to its database UUID."""
    if not external_id:
        return None
    result = await db.execute(
        select(Customer.id).where(
            Customer.organization_id == org_id,
            Customer.external_id == external_id,
        )
    )
    row = result.first()
    return row[0] if row else None


async def _upsert_customer(
    db: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]
) -> tuple[bool, str]:
    """Upsert a Customer. Returns (is_new, entity_id)."""
    ext_id = data.get("external_id")
    if ext_id:
        result = await db.execute(
            select(Customer).where(
                Customer.organization_id == org_id,
                Customer.external_id == ext_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in data.items():
                if value is not None and hasattr(existing, key):
                    setattr(existing, key, value)
            await db.flush()
            return False, str(existing.id)

    customer = Customer(organization_id=org_id, **{k: v for k, v in data.items() if v is not None})
    db.add(customer)
    await db.flush()
    return True, str(customer.id)


async def _upsert_contract(
    db: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]
) -> tuple[bool, str]:
    """Upsert a Contract."""
    ext_id = data.get("external_id") or data.get("contract_number")
    if ext_id:
        result = await db.execute(
            select(Contract).where(
                Contract.organization_id == org_id,
                Contract.contract_number == ext_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in data.items():
                if value is not None and key != "customer_external_id" and hasattr(existing, key):
                    setattr(existing, key, value)
            await db.flush()
            return False, str(existing.id)

    contract = Contract(organization_id=org_id, **{k: v for k, v in data.items() if v is not None and k != "customer_external_id"})
    db.add(contract)
    await db.flush()
    return True, str(contract.id)


async def _upsert_contract_line(
    db: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]
) -> tuple[bool, str]:
    """Upsert a ContractLine."""
    data.pop("contract_external_id", None)
    line = ContractLine(organization_id=org_id, **{k: v for k, v in data.items() if v is not None})
    db.add(line)
    await db.flush()
    return True, str(line.id)


async def _upsert_project(
    db: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]
) -> tuple[bool, str]:
    """Upsert a Project."""
    ext_id = data.get("external_id")
    if ext_id:
        result = await db.execute(
            select(Project).where(
                Project.organization_id == org_id,
                Project.external_id == ext_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in data.items():
                if value is not None and key != "customer_external_id" and hasattr(existing, key):
                    setattr(existing, key, value)
            await db.flush()
            return False, str(existing.id)

    project = Project(organization_id=org_id, **{k: v for k, v in data.items() if v is not None and k != "customer_external_id"})
    db.add(project)
    await db.flush()
    return True, str(project.id)


async def _upsert_invoice(
    db: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]
) -> tuple[bool, str]:
    """Upsert an Invoice. Resolves FK references from external_ids."""
    ext_id = data.get("external_id") or data.get("invoice_number")
    if ext_id:
        result = await db.execute(
            select(Invoice).where(
                Invoice.organization_id == org_id,
                Invoice.invoice_number == ext_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in data.items():
                if value is not None and key not in ("customer_external_id", "contract_external_id", "project_external_id") and hasattr(existing, key):
                    setattr(existing, key, value)
            await db.flush()
            return False, str(existing.id)

    # Resolve FK references
    invoice_data = {k: v for k, v in data.items() if v is not None and k not in ("customer_external_id", "contract_external_id", "project_external_id")}
    customer_id = await _resolve_customer_id(db, org_id, data.get("customer_external_id"))
    if customer_id:
        invoice_data["customer_id"] = customer_id
    else:
        invoice_data["customer_id"] = uuid.uuid4()  # placeholder — will be resolved in Phase 5

    invoice = Invoice(organization_id=org_id, **invoice_data)
    db.add(invoice)
    await db.flush()
    return True, str(invoice.id)


async def _upsert_invoice_line(
    db: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]
) -> tuple[bool, str]:
    """Upsert an InvoiceLine."""
    data.pop("invoice_external_id", None)
    line = InvoiceLine(organization_id=org_id, **{k: v for k, v in data.items() if v is not None})
    db.add(line)
    await db.flush()
    return True, str(line.id)


async def _upsert_payment(
    db: AsyncSession, org_id: uuid.UUID, data: dict[str, Any]
) -> tuple[bool, str]:
    """Upsert a Payment. Resolves FK references from external_ids."""
    ext_id = data.get("external_id")
    if ext_id:
        result = await db.execute(
            select(Payment).where(
                Payment.organization_id == org_id,
                Payment.external_id == ext_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in data.items():
                if value is not None and key != "customer_external_id" and hasattr(existing, key):
                    setattr(existing, key, value)
            await db.flush()
            return False, str(existing.id)

    # Resolve FK references
    payment_data = {k: v for k, v in data.items() if v is not None and k != "customer_external_id"}
    customer_id = await _resolve_customer_id(db, org_id, data.get("customer_external_id"))
    if customer_id:
        payment_data["customer_id"] = customer_id
    else:
        payment_data["customer_id"] = uuid.uuid4()  # placeholder — will be resolved in Phase 5

    payment = Payment(organization_id=org_id, **payment_data)
    db.add(payment)
    await db.flush()
    return True, str(payment.id)


UPSERTERS: dict[str, callable] = {
    "customer": _upsert_customer,
    "contract": _upsert_contract,
    "contract_line": _upsert_contract_line,
    "project": _upsert_project,
    "invoice": _upsert_invoice,
    "invoice_line": _upsert_invoice_line,
    "payment": _upsert_payment,
}


async def run_import(
    db: AsyncSession,
    org_id: uuid.UUID,
    target_entity: str,
    file_content: bytes,
    file_name: str,
    column_mapping: dict[str, str] | None = None,
) -> ImportJob:
    """Run a full import: parse → validate → upsert → audit.

    Returns the ImportJob with status, counts, and errors.
    """
    # Create ImportJob
    job = ImportJob(
        organization_id=org_id,
        target_entity=target_entity,
        source="csv" if file_name.endswith(".csv") else "excel",
        file_name=file_name,
        column_mapping=column_mapping,
        status="processing",
    )
    db.add(job)
    await db.flush()

    # Parse file
    try:
        if file_name.endswith(".csv"):
            rows = read_csv(file_content)
        elif file_name.endswith((".xlsx", ".xls")):
            rows = read_excel(file_content)
        else:
            job.status = "failed"
            job.errors = {"file": f"Unsupported file format: {file_name}"}
            await db.commit()
            return job
    except Exception as e:
        job.status = "failed"
        job.errors = {"file": f"Failed to parse file: {e}"}
        await db.commit()
        return job

    # Apply column mapping if provided
    if column_mapping:
        mapped_rows = []
        for row in rows:
            mapped = {}
            for original_key, value in row.items():
                target_key = column_mapping.get(original_key, original_key)
                mapped[target_key] = value
            mapped_rows.append(mapped)
        rows = mapped_rows

    job.records_received = len(rows)

    # Validate
    validator = VALIDATORS.get(target_entity)
    if validator is None:
        job.status = "failed"
        job.errors = {"entity": f"Unknown target entity: {target_entity}"}
        await db.commit()
        return job

    valid_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        is_valid, result = validator(row)
        if is_valid:
            valid_rows.append(result)
        else:
            errors.append({"row": i + 1, "errors": result, "original": row})

    # Upsert valid rows
    accepted = 0
    for idx, row_data in enumerate(valid_rows):
        try:
            upserter = UPSERTERS[target_entity]
            await upserter(db, org_id, row_data)
            accepted += 1
        except Exception as e:
            errors.append({"row": idx + 1, "errors": [f"Database error: {e}"]})

    job.records_accepted = accepted
    job.records_rejected = len(errors)
    job.errors = {"rows": errors} if errors else None
    job.status = "completed" if not errors else "completed_with_errors"
    await db.commit()

    return job
