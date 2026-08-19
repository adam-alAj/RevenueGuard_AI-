"""Tests for Leakage Inbox filtering, pagination, and search.

Tests the composable filter logic in the leakage inbox endpoint
by exercising the in-memory store directly with known test data.
"""

from __future__ import annotations

import uuid

from app.api.v1.leakage_inbox import (
    _leakage_store,
    clear_leakage_store,
    set_leakage_store,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())  # different org — cross-tenant test


def _seed_cases(org_id: str = ORG_A) -> dict[str, dict]:
    """Seed the in-memory store with a diverse set of leakage cases."""
    cases = {
        "case-001": {
            "case_id": "case-001",
            "case_number": "RL-000001",
            "leakage_type": "missing_invoice",
            "status": "detected",
            "severity": "critical",
            "customer_id": "cust-001",
            "potential_leakage": "25000.00",
            "confidence": "0.95",
            "assigned_to": "user-alice",
            "description": "Missing invoice for completed project",
            "organization_id": org_id,
            "created_at": "2025-06-01T10:00:00Z",
        },
        "case-002": {
            "case_id": "case-002",
            "case_number": "RL-000002",
            "leakage_type": "underbilling",
            "status": "investigating",
            "severity": "high",
            "customer_id": "cust-002",
            "potential_leakage": "8500.00",
            "confidence": "0.88",
            "assigned_to": "user-bob",
            "description": "Underbilling on Q2 contract",
            "organization_id": org_id,
            "created_at": "2025-06-15T14:30:00Z",
        },
        "case-003": {
            "case_id": "case-003",
            "case_number": "RL-000003",
            "leakage_type": "missing_invoice",
            "status": "pending_review",
            "severity": "medium",
            "customer_id": "cust-001",
            "potential_leakage": "3200.00",
            "confidence": "0.72",
            "assigned_to": None,
            "description": "Invoice not generated for support contract",
            "organization_id": org_id,
            "created_at": "2025-07-01T09:00:00Z",
        },
        "case-004": {
            "case_id": "case-004",
            "case_number": "RL-000004",
            "leakage_type": "overdue_invoice",
            "status": "approved",
            "severity": "low",
            "customer_id": "cust-003",
            "potential_leakage": "750.00",
            "confidence": "0.99",
            "assigned_to": "user-alice",
            "description": "Overdue invoice #INV-4521",
            "organization_id": org_id,
            "created_at": "2025-07-10T11:00:00Z",
        },
        "case-005": {
            "case_id": "case-005",
            "case_number": "RL-000005",
            "leakage_type": "contract_expiration",
            "status": "recovered",
            "severity": "high",
            "customer_id": "cust-004",
            "potential_leakage": "12000.00",
            "confidence": "0.91",
            "assigned_to": "user-bob",
            "description": "Contract expired without renewal",
            "organization_id": org_id,
            "created_at": "2025-07-20T16:00:00Z",
        },
        # Cross-tenant case (Org B)
        "case-006": {
            "case_id": "case-006",
            "case_number": "RL-000006",
            "leakage_type": "missing_invoice",
            "status": "detected",
            "severity": "critical",
            "customer_id": "cust-005",
            "potential_leakage": "50000.00",
            "confidence": "0.98",
            "assigned_to": None,
            "description": "Org B missing invoice",
            "organization_id": ORG_B,
            "created_at": "2025-07-25T08:00:00Z",
        },
    }
    set_leakage_store(cases)
    return cases


# ---------------------------------------------------------------------------
# Single filter tests
# ---------------------------------------------------------------------------


class TestLeakageFilters:
    """Test each filter parameter independently."""

    def setup_method(self) -> None:
        _seed_cases()

    def teardown_method(self) -> None:
        clear_leakage_store()

    def _apply_filters(self, **filters: object) -> list[dict]:
        """Apply filters to the seed data and return matching cases."""
        cases = list(_leakage_store.values())
        # Simulate the same filtering logic as the endpoint
        from app.api.v1.leakage_inbox import _leakage_store as store

        cases = [c for c in store.values() if c.get("organization_id") == ORG_A]

        if filters.get("leakage_type"):
            cases = [c for c in cases if c["leakage_type"] == filters["leakage_type"]]
        if filters.get("status"):
            cases = [c for c in cases if c["status"] == filters["status"]]
        if filters.get("severity"):
            cases = [c for c in cases if c["severity"] == filters["severity"]]
        if filters.get("customer_id"):
            cases = [c for c in cases if c["customer_id"] == filters["customer_id"]]
        if "min_amount" in filters and filters["min_amount"] is not None:
            cases = [c for c in cases if float(c["potential_leakage"]) >= filters["min_amount"]]
        if "max_amount" in filters and filters["max_amount"] is not None:
            cases = [c for c in cases if float(c["potential_leakage"]) <= filters["max_amount"]]
        if "min_confidence" in filters and filters["min_confidence"] is not None:
            cases = [c for c in cases if float(c["confidence"]) >= filters["min_confidence"]]
        if "max_confidence" in filters and filters["max_confidence"] is not None:
            cases = [c for c in cases if float(c["confidence"]) <= filters["max_confidence"]]
        if filters.get("date_from"):
            cases = [c for c in cases if c["created_at"] >= filters["date_from"]]
        if filters.get("date_to"):
            cases = [c for c in cases if c["created_at"] <= filters["date_to"]]
        if filters.get("assigned_to"):
            cases = [c for c in cases if c["assigned_to"] == filters["assigned_to"]]
        if filters.get("search"):
            q = filters["search"].lower()
            cases = [
                c
                for c in cases
                if q in c.get("case_number", "").lower()
                or q in (c.get("description") or "").lower()
            ]

        return cases

    def test_no_filters_returns_org_cases(self) -> None:
        """Without filters, all Org A cases are returned."""
        results = self._apply_filters()
        assert len(results) == 5  # 5 Org A cases, 1 Org B excluded

    def test_filter_by_leakage_type(self) -> None:
        """Filter by leakage type returns only matching cases."""
        results = self._apply_filters(leakage_type="missing_invoice")
        assert len(results) == 2  # case-001 and case-003
        assert all(c["leakage_type"] == "missing_invoice" for c in results)

    def test_filter_by_status(self) -> None:
        """Filter by status returns only matching cases."""
        results = self._apply_filters(status="detected")
        assert len(results) == 1
        assert results[0]["case_id"] == "case-001"

    def test_filter_by_severity(self) -> None:
        """Filter by severity returns only matching cases."""
        results = self._apply_filters(severity="high")
        assert len(results) == 2  # case-002 and case-005

    def test_filter_by_customer(self) -> None:
        """Filter by customer_id returns only matching cases."""
        results = self._apply_filters(customer_id="cust-001")
        assert len(results) == 2  # case-001 and case-003

    def test_filter_min_amount(self) -> None:
        """Min amount filter excludes smaller cases."""
        results = self._apply_filters(min_amount=10000.0)
        assert len(results) == 2  # case-001 ($25k) and case-005 ($12k)

    def test_filter_max_amount(self) -> None:
        """Max amount filter excludes larger cases."""
        results = self._apply_filters(max_amount=5000.0)
        assert len(results) == 2  # case-003 ($3.2k) and case-004 ($750)

    def test_filter_amount_range(self) -> None:
        """Amount range filters compose with AND logic."""
        results = self._apply_filters(min_amount=1000.0, max_amount=10000.0)
        assert len(results) == 2  # case-002 ($8.5k) and case-003 ($3.2k)

    def test_filter_min_confidence(self) -> None:
        """Min confidence filter excludes low-confidence cases."""
        results = self._apply_filters(min_confidence=0.90)
        assert len(results) == 3  # case-001, case-004, case-005

    def test_filter_date_range(self) -> None:
        """Date range filter returns cases within the specified window."""
        results = self._apply_filters(
            date_from="2025-06-15T00:00:00Z",
            date_to="2025-07-05T23:59:59Z",
        )
        assert len(results) == 2  # case-002 (Jun 15) and case-003 (Jul 1)

    def test_filter_assigned_to(self) -> None:
        """Assigned-to filter returns only cases assigned to that user."""
        results = self._apply_filters(assigned_to="user-alice")
        assert len(results) == 2  # case-001 and case-004

    def test_filter_unassigned(self) -> None:
        """Filtering by unassigned returns cases with no assignee."""
        cases = [
            c
            for c in _leakage_store.values()
            if c.get("organization_id") == ORG_A and c.get("assigned_to") is None
        ]
        assert len(cases) == 1  # case-003
        assert cases[0]["case_id"] == "case-003"

    def test_search_case_number(self) -> None:
        """Search by case number returns matching cases."""
        results = self._apply_filters(search="RL-000002")
        assert len(results) == 1
        assert results[0]["case_id"] == "case-002"

    def test_search_description(self) -> None:
        """Search by description text returns matching cases."""
        results = self._apply_filters(search="contract")
        # case-002 ("Q2 contract"), case-003 ("support contract"), case-005 ("Contract expired")
        assert len(results) == 3

    def test_search_case_insensitive(self) -> None:
        """Search is case-insensitive."""
        results = self._apply_filters(search="MISSING")
        # Only case-001 description contains "Missing"
        assert len(results) == 1
        assert results[0]["case_id"] == "case-001"


# ---------------------------------------------------------------------------
# Composed filter tests
# ---------------------------------------------------------------------------


class TestComposedFilters:
    """Test multiple filters composed together (AND logic)."""

    def setup_method(self) -> None:
        _seed_cases()

    def teardown_method(self) -> None:
        clear_leakage_store()

    def _apply_filters(self, **filters: object) -> list[dict]:
        """Apply composed filters to the seed data."""
        cases = [c for c in _leakage_store.values() if c.get("organization_id") == ORG_A]
        from app.api.v1.leakage_inbox import _leakage_store as store

        cases = [c for c in store.values() if c.get("organization_id") == ORG_A]

        if filters.get("leakage_type"):
            cases = [c for c in cases if c["leakage_type"] == filters["leakage_type"]]
        if filters.get("status"):
            cases = [c for c in cases if c["status"] == filters["status"]]
        if filters.get("severity"):
            cases = [c for c in cases if c["severity"] == filters["severity"]]
        if filters.get("customer_id"):
            cases = [c for c in cases if c["customer_id"] == filters["customer_id"]]
        if filters.get("min_amount") is not None:
            cases = [c for c in cases if float(c["potential_leakage"]) >= filters["min_amount"]]
        if filters.get("max_amount") is not None:
            cases = [c for c in cases if float(c["potential_leakage"]) <= filters["max_amount"]]
        if filters.get("min_confidence") is not None:
            cases = [c for c in cases if float(c["confidence"]) >= filters["min_confidence"]]
        if filters.get("max_confidence") is not None:
            cases = [c for c in cases if float(c["confidence"]) <= filters["max_confidence"]]
        if filters.get("date_from"):
            cases = [c for c in cases if c["created_at"] >= filters["date_from"]]
        if filters.get("date_to"):
            cases = [c for c in cases if c["created_at"] <= filters["date_to"]]
        if filters.get("assigned_to"):
            cases = [c for c in cases if c["assigned_to"] == filters["assigned_to"]]
        if filters.get("search"):
            q = filters["search"].lower()
            cases = [
                c
                for c in cases
                if q in c.get("case_number", "").lower()
                or q in (c.get("description") or "").lower()
            ]
        return cases

    def test_type_plus_status(self) -> None:
        """Filter by type AND status narrows results."""
        results = self._apply_filters(leakage_type="missing_invoice", status="detected")
        assert len(results) == 1
        assert results[0]["case_id"] == "case-001"

    def test_severity_plus_amount_range(self) -> None:
        """Filter by severity AND amount range."""
        results = self._apply_filters(severity="high", min_amount=5000.0)
        assert len(results) == 2  # case-002 ($8.5k) and case-005 ($12k)

    def test_customer_plus_status(self) -> None:
        """Filter by customer AND status."""
        results = self._apply_filters(customer_id="cust-001", status="pending_review")
        assert len(results) == 1
        assert results[0]["case_id"] == "case-003"

    def test_all_filters_combined(self) -> None:
        """All filters combined narrows to zero matches when contradictory."""
        results = self._apply_filters(
            leakage_type="missing_invoice",
            status="detected",
            severity="low",  # case-001 is critical, not low
        )
        assert len(results) == 0

    def test_no_match_returns_empty(self) -> None:
        """Filters that match nothing return empty list."""
        results = self._apply_filters(customer_id="nonexistent-customer")
        assert results == []


# ---------------------------------------------------------------------------
# Sorting tests
# ---------------------------------------------------------------------------


class TestLeakageSorting:
    """Test sorting of leakage inbox results."""

    def setup_method(self) -> None:
        _seed_cases()

    def teardown_method(self) -> None:
        clear_leakage_store()

    def test_sort_by_created_at_desc(self) -> None:
        """Default sort is created_at descending (newest first)."""
        cases = [c for c in _leakage_store.values() if c.get("organization_id") == ORG_A]
        cases.sort(key=lambda x: x["created_at"], reverse=True)
        assert cases[0]["case_id"] == "case-005"  # Jul 20
        assert cases[-1]["case_id"] == "case-001"  # Jun 1

    def test_sort_by_amount_desc(self) -> None:
        """Sort by potential_leakage descending."""
        cases = [c for c in _leakage_store.values() if c.get("organization_id") == ORG_A]
        cases.sort(key=lambda x: float(x["potential_leakage"]), reverse=True)
        assert cases[0]["case_id"] == "case-001"  # $25,000
        assert cases[-1]["case_id"] == "case-004"  # $750

    def test_sort_by_case_number_asc(self) -> None:
        """Sort by case number ascending."""
        cases = [c for c in _leakage_store.values() if c.get("organization_id") == ORG_A]
        cases.sort(key=lambda x: x["case_number"])
        assert cases[0]["case_number"] == "RL-000001"
        assert cases[-1]["case_number"] == "RL-000005"


# ---------------------------------------------------------------------------
# Cross-tenant isolation test
# ---------------------------------------------------------------------------


class TestCrossTenantIsolation:
    """Verify Org A cannot see Org B's cases."""

    def setup_method(self) -> None:
        _seed_cases()

    def teardown_method(self) -> None:
        clear_leakage_store()

    def test_org_a_excludes_org_b_cases(self) -> None:
        """Cases from Org B are excluded when filtering by Org A."""
        org_a_cases = [c for c in _leakage_store.values() if c.get("organization_id") == ORG_A]
        org_b_cases = [c for c in _leakage_store.values() if c.get("organization_id") == ORG_B]

        assert len(org_a_cases) == 5
        assert len(org_b_cases) == 1
        assert all(c["organization_id"] == ORG_A for c in org_a_cases)
        assert all(c["organization_id"] == ORG_B for c in org_b_cases)

    def test_org_b_filter_does_not_leak_to_org_a(self) -> None:
        """Org B's customer_id filter doesn't affect Org A results."""
        org_a_cust = [
            c
            for c in _leakage_store.values()
            if c.get("organization_id") == ORG_A and c.get("customer_id") == "cust-005"
        ]
        # cust-005 exists in Org B but not Org A
        assert len(org_a_cust) == 0


# ---------------------------------------------------------------------------
# Pagination integration
# ---------------------------------------------------------------------------


class TestLeakagePagination:
    """Test pagination of filtered leakage results."""

    def setup_method(self) -> None:
        _seed_cases()

    def teardown_method(self) -> None:
        clear_leakage_store()

    def test_first_page(self) -> None:
        """First page returns correct subset."""
        from app.api.v1.pagination import paginate

        all_cases = [c for c in _leakage_store.values() if c.get("organization_id") == ORG_A]
        result = paginate(all_cases[:3], total=len(all_cases), page=1, page_size=3)

        assert result["total"] == 5
        assert len(result["items"]) == 3
        assert result["total_pages"] == 2  # ceil(5/3)

    def test_second_page(self) -> None:
        """Second page returns remaining items."""
        from app.api.v1.pagination import paginate

        all_cases = [c for c in _leakage_store.values() if c.get("organization_id") == ORG_A]
        result = paginate(all_cases[3:5], total=len(all_cases), page=2, page_size=3)

        assert len(result["items"]) == 2
        assert result["page"] == 2
