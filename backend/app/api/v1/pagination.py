"""Shared pagination, filtering, and sorting utilities for list endpoints.

Every list endpoint uses these utilities to ensure consistency:
- Cursor-based or offset pagination with sane defaults
- Max page size enforcement
- Default sort order
- Filter parameter validation
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams:
    """Standard pagination parameters for list endpoints."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ) -> None:
        self.page = page
        self.page_size = min(page_size, 100)  # Enforce max
        self.offset = (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def paginate(
    items: Sequence[Any],
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Create a paginated response dict.

    Args:
        items: The items for the current page.
        total: Total count of matching items.
        page: Current page number.
        page_size: Items per page.

    Returns:
        Dict with items, total, page, page_size, total_pages.
    """
    total_pages = max(1, -(-total // page_size))  # Ceiling division
    return {
        "items": list(items),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@dataclass
class LeakageFilters:
    """Composable filters for the Leakage Inbox."""

    leakage_type: str | None = None
    status: str | None = None
    severity: str | None = None
    customer_id: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    date_from: str | None = None
    date_to: str | None = None
    assigned_to: str | None = None
    search: str | None = None


def get_leakage_filters(
    leakage_type: str | None = Query(None, description="Filter by leakage type"),
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    customer_id: str | None = Query(None, description="Filter by customer ID"),
    min_amount: float | None = Query(None, description="Min potential leakage amount"),
    max_amount: float | None = Query(None, description="Max potential leakage amount"),
    min_confidence: float | None = Query(None, ge=0, le=1, description="Min confidence"),
    max_confidence: float | None = Query(None, ge=0, le=1, description="Max confidence"),
    date_from: str | None = Query(None, description="Start date (ISO 8601)"),
    date_to: str | None = Query(None, description="End date (ISO 8601)"),
    assigned_to: str | None = Query(None, description="Filter by assigned user ID"),
    search: str | None = Query(None, description="Search in case number/description"),
) -> LeakageFilters:
    """Extract leakage inbox filter parameters."""
    return LeakageFilters(
        leakage_type=leakage_type,
        status=status,
        severity=severity,
        customer_id=customer_id,
        min_amount=min_amount,
        max_amount=max_amount,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        date_from=date_from,
        date_to=date_to,
        assigned_to=assigned_to,
        search=search,
    )
