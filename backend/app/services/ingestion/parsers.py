"""CSV and Excel file parsers with column normalization.

Handles messy real-world exports from QuickBooks, spreadsheets, CRM exports.
Normalizes column names (lowercase, snake_case, stripped), parses monetary
amounts ($1,200.00 → Decimal), and handles common date formats.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_column_name(name: str) -> str:
    """Normalize a column name to lowercase snake_case."""
    import re

    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name


def parse_money(value: Any) -> Decimal | None:
    """Parse a messy monetary string into Decimal.

    Handles: "$1,200.00", "1200.00", "1,200", "$1200", "", None, etc.
    Returns None for empty/unparseable values (caller decides if required).
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Strip currency symbols and whitespace
    s = s.replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_date(value: Any) -> str | None:
    """Parse a date string, returning ISO format (YYYY-MM-DD) or None.

    Handles common formats: MM/DD/YYYY, M/D/YY, YYYY-MM-DD, etc.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    from datetime import datetime

    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%m-%d-%Y",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_integer(value: Any) -> int | None:
    """Parse an integer, handling commas and whitespace."""
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def parse_string(value: Any) -> str | None:
    """Parse a string, returning None for empty/whitespace-only."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def read_csv(file_content: bytes) -> list[dict[str, Any]]:
    """Read CSV file content and return normalized rows.

    Returns list of dicts with normalized column names.
    """
    text = file_content.decode("utf-8-sig")  # Handle BOM
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        normalized = {}
        for key, value in row.items():
            if key is not None:
                normalized[normalize_column_name(key)] = value
        rows.append(normalized)
    return rows


def read_excel(file_content: bytes) -> list[dict[str, Any]]:
    """Read Excel file content and return normalized rows.

    Returns list of dicts with normalized column names.
    """
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers = next(rows_iter, None)
    if headers is None:
        return []

    normalized_headers = [
        normalize_column_name(str(h)) if h else f"col_{i}" for i, h in enumerate(headers)
    ]
    rows = []
    for row in rows_iter:
        row_dict = {}
        for i, value in enumerate(row):
            if i < len(normalized_headers):
                row_dict[normalized_headers[i]] = value
        rows.append(row_dict)
    wb.close()
    return rows
