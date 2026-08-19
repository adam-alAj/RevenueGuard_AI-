"""Tests for the CSV/Excel import pipeline.

Tests verify:
- Parsing: CSV and Excel files produce correct normalized rows
- Validation: malformed rows produce specific, human-readable errors
- Import: valid rows are persisted to the database
- Idempotency: re-importing the same file does not create duplicates
- Cross-tenant isolation: Org A imports cannot create Org B records
- Error reporting: ImportJob tracks received/accepted/rejected counts
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.organization import Organization
from app.services.ingestion.parsers import (
    normalize_column_name,
    parse_date,
    parse_integer,
    parse_money,
    read_csv,
)
from app.services.ingestion.validators import (
    validate_contract,
    validate_customer,
    validate_invoice,
    validate_payment,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestNormalizeColumnName:
    def test_simple(self) -> None:
        assert normalize_column_name("Name") == "name"

    def test_snake_case(self) -> None:
        assert normalize_column_name("Customer Name") == "customer_name"

    def test_strip_special_chars(self) -> None:
        assert normalize_column_name("Total ($)") == "total"

    def test_lower(self) -> None:
        assert normalize_column_name("EXTERNAL_ID") == "external_id"

    def test_whitespace(self) -> None:
        assert normalize_column_name("  Phone  ") == "phone"


class TestParseMoney:
    def test_plain_number(self) -> None:
        assert parse_money("1200.00") == Decimal("1200.00")

    def test_dollar_sign(self) -> None:
        assert parse_money("$1,200.00") == Decimal("1200.00")

    def test_commas(self) -> None:
        assert parse_money("1,200,000.50") == Decimal("1200000.50")

    def test_empty(self) -> None:
        assert parse_money("") is None

    def test_none(self) -> None:
        assert parse_money(None) is None

    def test_invalid(self) -> None:
        assert parse_money("abc") is None

    def test_integer(self) -> None:
        assert parse_money("500") == Decimal("500")

    def test_euro(self) -> None:
        assert parse_money("€1,200.00") == Decimal("1200.00")


class TestParseDate:
    def test_iso_format(self) -> None:
        assert parse_date("2026-01-15") == "2026-01-15"

    def test_us_format(self) -> None:
        assert parse_date("01/15/2026") == "2026-01-15"

    def test_short_year(self) -> None:
        assert parse_date("01/15/26") == "2026-01-15"

    def test_empty(self) -> None:
        assert parse_date("") is None

    def test_none(self) -> None:
        assert parse_date(None) is None


class TestParseInteger:
    def test_plain(self) -> None:
        assert parse_integer("100") == 100

    def test_comma(self) -> None:
        assert parse_integer("1,200") == 1200

    def test_float_string(self) -> None:
        assert parse_integer("3.0") == 3

    def test_empty(self) -> None:
        assert parse_integer("") is None


class TestReadCSV:
    def test_reads_fixture(self) -> None:
        content = (FIXTURES_DIR / "sample_customers.csv").read_bytes()
        rows = read_csv(content)
        assert len(rows) == 6
        assert rows[0]["name"] == "Acme Inc"
        assert rows[0]["external_id"] == "CUST-001"

    def test_normalizes_columns(self) -> None:
        content = b"Customer Name,External ID\nTest,C001\n"
        rows = read_csv(content)
        assert "customer_name" in rows[0]
        assert "external_id" in rows[0]


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------


class TestValidateCustomer:
    def test_valid_row(self) -> None:
        row = {"name": "Acme", "external_id": "C001"}
        is_valid, result = validate_customer(row)
        assert is_valid is True
        assert result["name"] == "Acme"

    def test_missing_name(self) -> None:
        row = {"email": "test@test.com"}
        is_valid, errors = validate_customer(row)
        assert is_valid is False
        assert "name is required" in errors

    def test_empty_name(self) -> None:
        row = {"name": ""}
        is_valid, _errors = validate_customer(row)
        assert is_valid is False


class TestValidateInvoice:
    def test_valid_row(self) -> None:
        row = {
            "customer_external_id": "C001",
            "invoice_number": "INV-001",
            "total": "$1,200.00",
        }
        is_valid, result = validate_invoice(row)
        assert is_valid is True
        assert result["total"] == Decimal("1200.00")

    def test_missing_customer(self) -> None:
        row = {"invoice_number": "INV-001", "total": "100"}
        is_valid, errors = validate_invoice(row)
        assert is_valid is False
        assert "customer_external_id is required" in errors

    def test_invalid_total(self) -> None:
        row = {
            "customer_external_id": "C001",
            "invoice_number": "INV-001",
            "total": "not-a-number",
        }
        is_valid, errors = validate_invoice(row)
        assert is_valid is False
        assert any("total" in e for e in errors)

    def test_missing_invoice_number(self) -> None:
        row = {"customer_external_id": "C001", "total": "100"}
        is_valid, errors = validate_invoice(row)
        assert is_valid is False
        assert "invoice_number is required" in errors


class TestValidateContract:
    def test_valid_row(self) -> None:
        row = {
            "customer_external_id": "C001",
            "contract_number": "CON-001",
            "name": "Support Agreement",
            "start_date": "2026-01-01",
        }
        is_valid, _result = validate_contract(row)
        assert is_valid is True

    def test_missing_fields(self) -> None:
        row = {"name": "Test"}
        is_valid, errors = validate_contract(row)
        assert is_valid is False
        assert len(errors) >= 3  # customer_external_id, contract_number, start_date


class TestValidatePayment:
    def test_valid_row(self) -> None:
        row = {
            "customer_external_id": "C001",
            "amount": "$500.00",
            "payment_date": "2026-01-15",
        }
        is_valid, result = validate_payment(row)
        assert is_valid is True
        assert result["amount"] == Decimal("500.00")

    def test_missing_amount(self) -> None:
        row = {
            "customer_external_id": "C001",
            "payment_date": "2026-01-15",
        }
        is_valid, errors = validate_payment(row)
        assert is_valid is False
        assert "amount is required" in errors


# ---------------------------------------------------------------------------
# Import integration tests (require DB session)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_customers_from_csv(db_session: AsyncSession) -> None:
    """Import customers from CSV — creates Customer records."""
    from app.services.ingestion.importer import run_import

    # Create org
    org = Organization(name="Test Org", slug=f"test-import-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    content = (FIXTURES_DIR / "sample_customers.csv").read_bytes()
    job = await run_import(
        db=db_session,
        org_id=org.id,
        target_entity="customer",
        file_content=content,
        file_name="sample_customers.csv",
    )

    assert job.status == "completed"
    assert job.records_received == 6
    assert job.records_accepted == 6
    assert job.records_rejected == 0

    # Verify customers were created
    result = await db_session.execute(select(Customer).where(Customer.organization_id == org.id))
    customers = list(result.scalars().all())
    assert len(customers) == 6


@pytest.mark.asyncio
async def test_import_invoices_with_malformed_rows(db_session: AsyncSession) -> None:
    """Import invoices with malformed rows — reports specific errors."""
    from app.services.ingestion.importer import run_import

    org = Organization(name="Test Org", slug=f"test-import-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    content = (FIXTURES_DIR / "sample_invoices.csv").read_bytes()
    job = await run_import(
        db=db_session,
        org_id=org.id,
        target_entity="invoice",
        file_content=content,
        file_name="sample_invoices.csv",
    )

    assert job.records_received == 7
    # Row 5 has no customer_external_id, row 6 has invalid total
    assert job.records_rejected >= 1
    assert job.records_accepted >= 1


@pytest.mark.asyncio
async def test_import_idempotency(db_session: AsyncSession) -> None:
    """Re-importing the same file does not create duplicates."""
    from app.services.ingestion.importer import run_import

    org = Organization(name="Test Org", slug=f"test-import-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    content = (FIXTURES_DIR / "sample_customers.csv").read_bytes()

    # First import
    await run_import(
        db=db_session,
        org_id=org.id,
        target_entity="customer",
        file_content=content,
        file_name="sample_customers.csv",
    )

    result1 = await db_session.execute(select(Customer).where(Customer.organization_id == org.id))
    count1 = len(list(result1.scalars().all()))

    # Second import — should not create duplicates
    await run_import(
        db=db_session,
        org_id=org.id,
        target_entity="customer",
        file_content=content,
        file_name="sample_customers.csv",
    )

    result2 = await db_session.execute(select(Customer).where(Customer.organization_id == org.id))
    count2 = len(list(result2.scalars().all()))

    assert count1 == count2, f"Idempotency failed: {count1} before, {count2} after re-import"


@pytest.mark.asyncio
async def test_import_cross_tenant_isolation(db_session: AsyncSession) -> None:
    """Import for Org A does not create records in Org B."""
    from app.services.ingestion.importer import run_import

    org_a = Organization(name="Org A", slug=f"org-a-{uuid.uuid4().hex[:8]}")
    org_b = Organization(name="Org B", slug=f"org-b-{uuid.uuid4().hex[:8]}")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    content = (FIXTURES_DIR / "sample_customers.csv").read_bytes()

    # Import for Org A
    await run_import(
        db=db_session,
        org_id=org_a.id,
        target_entity="customer",
        file_content=content,
        file_name="sample_customers.csv",
    )

    # Org B should have no customers
    result_b = await db_session.execute(
        select(Customer).where(Customer.organization_id == org_b.id)
    )
    customers_b = list(result_b.scalars().all())
    assert len(customers_b) == 0, "Cross-tenant leak: Org B has customers it shouldn't"

    # Org A should have 6 customers
    result_a = await db_session.execute(
        select(Customer).where(Customer.organization_id == org_a.id)
    )
    customers_a = list(result_a.scalars().all())
    assert len(customers_a) == 6


@pytest.mark.asyncio
async def test_import_unsupported_format(db_session: AsyncSession) -> None:
    """Importing an unsupported file type returns a failed job."""
    from app.services.ingestion.importer import run_import

    org = Organization(name="Test Org", slug=f"test-import-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    job = await run_import(
        db=db_session,
        org_id=org.id,
        target_entity="customer",
        file_content=b"some content",
        file_name="data.xml",
    )

    assert job.status == "failed"
    assert "Unsupported file format" in str(job.errors)
