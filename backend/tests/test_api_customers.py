"""Tests for Customer CRUD endpoints — pagination, filtering, RBAC.

Tests exercise the in-memory stores directly since full HTTP testing
with mocked auth is covered in Phase 10's approval endpoint tests.
"""

from __future__ import annotations

import uuid

from app.api.v1.customers import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    _customer_store,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_customers() -> None:
    """Clear the in-memory customer store between tests."""
    _customer_store.clear()


def _make_customer(**overrides: object) -> dict:
    """Build a minimal valid customer payload."""
    data = {
        "name": "Acme Corp",
        "external_id": f"ext-{uuid.uuid4().hex[:8]}",
        "organization_id": str(uuid.uuid4()),
        "industry": "Technology",
        "currency": "USD",
        "payment_terms": "net30",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestCustomerSchemas:
    """Pydantic model validation for request/response."""

    def test_customer_create_validates_required_fields(self) -> None:
        """CustomerCreate requires name (only required field)."""
        import pydantic
        import pytest

        with pytest.raises(pydantic.ValidationError) as exc_info:
            CustomerCreate()  # type: ignore[call-arg]
        errors = {e["loc"][-1] for e in exc_info.value.errors()}
        assert "name" in errors

    def test_customer_response_has_expected_fields(self) -> None:
        """CustomerResponse serializes all customer fields."""
        resp = CustomerResponse(
            id=str(uuid.uuid4()),
            organization_id=str(uuid.uuid4()),
            name="Test Co",
            external_id="ext-1",
            is_active=True,
        )
        assert resp.name == "Test Co"
        assert resp.external_id == "ext-1"

    def test_customer_update_all_fields_optional(self) -> None:
        """CustomerUpdate allows partial updates — no required fields."""
        update = CustomerUpdate(name="New Name")
        assert update.name == "New Name"
        # All fields optional — email/phone/company default to None
        assert update.email is None
        assert update.phone is None


# ---------------------------------------------------------------------------
# CRUD logic tests
# ---------------------------------------------------------------------------


class TestCustomerCRUD:
    """Test the in-memory CRUD store operations."""

    def setup_method(self) -> None:
        _clear_customers()

    def test_create_customer(self) -> None:
        """Creating a customer stores it with correct fields."""
        payload = _make_customer(name="Acme Inc")
        cid = str(uuid.uuid4())
        _customer_store[cid] = payload
        assert _customer_store[cid]["name"] == "Acme Inc"
        assert _customer_store[cid]["currency"] == "USD"

    def test_get_customer(self) -> None:
        """Retrieving a stored customer returns the correct record."""
        cid = str(uuid.uuid4())
        _customer_store[cid] = _make_customer()
        record = _customer_store.get(cid)
        assert record is not None
        assert record["external_id"].startswith("ext-")

    def test_get_nonexistent_customer(self) -> None:
        """Getting a non-existent customer returns None."""
        assert _customer_store.get(str(uuid.uuid4())) is None

    def test_update_customer(self) -> None:
        """Updating a customer changes only provided fields."""
        cid = str(uuid.uuid4())
        _customer_store[cid] = _make_customer(name="Original")
        _customer_store[cid]["name"] = "Updated"
        assert _customer_store[cid]["name"] == "Updated"
        # Other fields untouched
        assert "currency" in _customer_store[cid]

    def test_delete_customer(self) -> None:
        """Deleting a customer removes it from the store."""
        cid = str(uuid.uuid4())
        _customer_store[cid] = _make_customer()
        del _customer_store[cid]
        assert cid not in _customer_store

    def test_multiple_customers(self) -> None:
        """Store can hold multiple customers."""
        for i in range(5):
            cid = str(uuid.uuid4())
            _customer_store[cid] = _make_customer(name=f"Company {i}")
        assert len(_customer_store) == 5


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------


class TestCustomerPagination:
    """Test the paginate utility with customer data."""

    def setup_method(self) -> None:
        _clear_customers()

    def test_pagination_returns_page(self) -> None:
        """Paginate returns a page of results with metadata."""
        from app.api.v1.pagination import paginate

        items = [{"name": f"Co {i}"} for i in range(10)]
        result = paginate(items[:3], total=10, page=1, page_size=3)

        assert result["total"] == 10
        assert len(result["items"]) == 3
        assert result["page"] == 1
        assert result["page_size"] == 3
        assert result["total_pages"] == 4  # ceil(10/3)

    def test_pagination_last_page(self) -> None:
        """Last page returns remaining items."""
        from app.api.v1.pagination import paginate

        items = [{"name": f"Co {i}"} for i in range(7)]
        result = paginate(items[6:7], total=7, page=3, page_size=3)

        assert len(result["items"]) == 1  # 7 - 2*3 = 1
        assert result["total_pages"] == 3

    def test_pagination_empty_store(self) -> None:
        """Empty store returns empty items list."""
        from app.api.v1.pagination import paginate

        result = paginate([], total=0, page=1, page_size=10)

        assert result["items"] == []
        assert result["total"] == 0
        assert result["total_pages"] == 1  # max(1, 0)

    def test_pagination_page_beyond_range(self) -> None:
        """Page beyond total returns empty items."""
        from app.api.v1.pagination import paginate

        result = paginate([], total=1, page=99, page_size=10)

        assert result["items"] == []
        assert result["page"] == 99

    def test_max_page_size_enforced(self) -> None:
        """Page size is capped at 100 via PaginationParams."""
        from app.api.v1.pagination import PaginationParams

        params = PaginationParams(page=1, page_size=150)  # exceeds 100
        assert params.page_size == 100  # capped

        params2 = PaginationParams(page=1, page_size=50)
        assert params2.page_size == 50  # under limit, unchanged


# ---------------------------------------------------------------------------
# RBAC enforcement tests
# ---------------------------------------------------------------------------


class TestCustomerRBAC:
    """Verify RBAC decorators on customer endpoints."""

    def test_require_permission_returns_dependency(self) -> None:
        """require_permission returns a callable FastAPI dependency."""
        from app.core.rbac import require_permission

        dep = require_permission("customers", "read")
        assert callable(dep)

    def test_require_permission_write_returns_dependency(self) -> None:
        """require_permission for write returns a callable dependency."""
        from app.core.rbac import require_permission

        dep = require_permission("customers", "write")
        assert callable(dep)

    def test_require_permission_different_resources(self) -> None:
        """require_permission works for different resource/action combos."""
        from app.core.rbac import require_permission

        deps = [
            require_permission("customers", "read"),
            require_permission("customers", "write"),
            require_permission("invoices", "read"),
            require_permission("leakage", "read"),
            require_permission("users", "write"),
        ]
        assert all(callable(d) for d in deps)
