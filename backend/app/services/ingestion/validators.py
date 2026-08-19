"""Per-row validators for the 7 MVP import entities.

Each validator takes a normalized row dict and returns:
- (True, cleaned_data) if the row is valid
- (False, list_of_error_strings) if the row is invalid

Every error message must be specific and human-readable — never "invalid row".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.ingestion.parsers import parse_date, parse_integer, parse_money, parse_string


class ValidationError(Exception):
    """Raised when a row fails validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


def _require(value: Any, field_name: str, errors: list[str]) -> Any:
    """Require a field to be non-empty, adding an error if missing."""
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{field_name} is required")
        return None
    return value


def _require_money(value: Any, field_name: str, errors: list[str]) -> Decimal | None:
    """Require a valid monetary amount."""
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{field_name} is required")
        return None
    parsed = parse_money(value)
    if parsed is None:
        errors.append(f"{field_name} must be a valid monetary amount, got '{value}'")
        return None
    return parsed


def _require_date(value: Any, field_name: str, errors: list[str]) -> str | None:
    """Require a valid date."""
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{field_name} is required")
        return None
    parsed = parse_date(value)
    if parsed is None:
        errors.append(
            f"{field_name} must be a valid date (YYYY-MM-DD or MM/DD/YYYY), got '{value}'"
        )
        return None
    return parsed


def _require_integer(value: Any, field_name: str, errors: list[str]) -> int | None:
    """Require a valid integer."""
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{field_name} is required")
        return None
    parsed = parse_integer(value)
    if parsed is None:
        errors.append(f"{field_name} must be a valid integer, got '{value}'")
        return None
    return parsed


# ---------------------------------------------------------------------------
# Entity validators
# ---------------------------------------------------------------------------


def validate_customer(row: dict[str, Any]) -> tuple[bool, dict[str, Any] | list[str]]:
    """Validate a Customer row. Requires: name."""
    errors: list[str] = []
    name = _require(row.get("name") or row.get("customer_name"), "name", errors)
    if errors:
        return False, errors
    return True, {
        "name": parse_string(name),
        "external_id": parse_string(row.get("external_id")),
        "email": parse_string(row.get("email")),
        "phone": parse_string(row.get("phone")),
        "address": parse_string(row.get("address")),
    }


def validate_contract(row: dict[str, Any]) -> tuple[bool, dict[str, Any] | list[str]]:
    """Validate a Contract row. Requires: customer_external_id, contract_number, name, start_date."""
    errors: list[str] = []
    customer_ext_id = _require(row.get("customer_external_id"), "customer_external_id", errors)
    contract_number = _require(row.get("contract_number"), "contract_number", errors)
    name = _require(row.get("name"), "name", errors)
    start_date = _require_date(row.get("start_date"), "start_date", errors)
    if errors:
        return False, errors
    return True, {
        "customer_external_id": parse_string(customer_ext_id),
        "contract_number": parse_string(contract_number),
        "name": parse_string(name),
        "start_date": start_date,
        "end_date": parse_date(row.get("end_date")),
        "total_value": parse_money(row.get("total_value")),
        "billing_frequency": parse_string(row.get("billing_frequency")),
    }


def validate_contract_line(row: dict[str, Any]) -> tuple[bool, dict[str, Any] | list[str]]:
    """Validate a ContractLine row. Requires: contract_external_id, description, quantity, unit_price."""
    errors: list[str] = []
    contract_ext_id = _require(row.get("contract_external_id"), "contract_external_id", errors)
    description = _require(row.get("description"), "description", errors)
    quantity = _require_integer(row.get("quantity"), "quantity", errors)
    unit_price = _require_money(row.get("unit_price"), "unit_price", errors)
    if errors:
        return False, errors
    return True, {
        "contract_external_id": parse_string(contract_ext_id),
        "description": parse_string(description),
        "quantity": quantity,
        "unit_price": unit_price,
        "total": (quantity * unit_price) if quantity and unit_price else None,
    }


def validate_project(row: dict[str, Any]) -> tuple[bool, dict[str, Any] | list[str]]:
    """Validate a Project row. Requires: customer_external_id, name."""
    errors: list[str] = []
    customer_ext_id = _require(row.get("customer_external_id"), "customer_external_id", errors)
    name = _require(row.get("name"), "name", errors)
    if errors:
        return False, errors
    return True, {
        "customer_external_id": parse_string(customer_ext_id),
        "name": parse_string(name),
        "external_id": parse_string(row.get("external_id")),
        "status": parse_string(row.get("status")) or "active",
        "start_date": parse_date(row.get("start_date")),
        "end_date": parse_date(row.get("end_date")),
        "is_billable": row.get("is_billable", "true").strip().lower() in ("true", "1", "yes"),
    }


def validate_invoice(row: dict[str, Any]) -> tuple[bool, dict[str, Any] | list[str]]:
    """Validate an Invoice row. Requires: customer_external_id, invoice_number, total."""
    errors: list[str] = []
    customer_ext_id = _require(row.get("customer_external_id"), "customer_external_id", errors)
    invoice_number = _require(row.get("invoice_number"), "invoice_number", errors)
    total = _require_money(row.get("total"), "total", errors)
    if errors:
        return False, errors
    return True, {
        "customer_external_id": parse_string(customer_ext_id),
        "invoice_number": parse_string(invoice_number),
        "external_id": parse_string(row.get("external_id")),
        "contract_external_id": parse_string(row.get("contract_external_id")),
        "project_external_id": parse_string(row.get("project_external_id")),
        "issued_date": parse_date(row.get("issued_date")),
        "due_date": parse_date(row.get("due_date")),
        "subtotal": parse_money(row.get("subtotal")),
        "tax_amount": parse_money(row.get("tax_amount")),
        "total": total,
        "outstanding_balance": parse_money(row.get("outstanding_balance")),
        "currency": parse_string(row.get("currency")) or "USD",
        "status": parse_string(row.get("status")) or "draft",
    }


def validate_invoice_line(row: dict[str, Any]) -> tuple[bool, dict[str, Any] | list[str]]:
    """Validate an InvoiceLine row. Requires: invoice_external_id, description, quantity, unit_price."""
    errors: list[str] = []
    invoice_ext_id = _require(row.get("invoice_external_id"), "invoice_external_id", errors)
    description = _require(row.get("description"), "description", errors)
    quantity = _require_integer(row.get("quantity"), "quantity", errors)
    unit_price = _require_money(row.get("unit_price"), "unit_price", errors)
    if errors:
        return False, errors
    return True, {
        "invoice_external_id": parse_string(invoice_ext_id),
        "description": parse_string(description),
        "quantity": quantity,
        "unit_price": unit_price,
        "total": (quantity * unit_price) if quantity and unit_price else None,
    }


def validate_payment(row: dict[str, Any]) -> tuple[bool, dict[str, Any] | list[str]]:
    """Validate a Payment row. Requires: customer_external_id, amount, payment_date."""
    errors: list[str] = []
    customer_ext_id = _require(row.get("customer_external_id"), "customer_external_id", errors)
    amount = _require_money(row.get("amount"), "amount", errors)
    payment_date = _require_date(row.get("payment_date"), "payment_date", errors)
    if errors:
        return False, errors
    return True, {
        "customer_external_id": parse_string(customer_ext_id),
        "amount": amount,
        "payment_date": payment_date,
        "external_id": parse_string(row.get("external_id")),
        "payment_number": parse_string(row.get("payment_number")),
        "payment_method": parse_string(row.get("payment_method")),
        "reference": parse_string(row.get("reference")),
        "currency": parse_string(row.get("currency")) or "USD",
    }


# Validator registry
VALIDATORS: dict[str, callable] = {
    "customer": validate_customer,
    "contract": validate_contract,
    "contract_line": validate_contract_line,
    "project": validate_project,
    "invoice": validate_invoice,
    "invoice_line": validate_invoice_line,
    "payment": validate_payment,
}
