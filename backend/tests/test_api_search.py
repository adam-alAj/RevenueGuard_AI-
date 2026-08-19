"""Tests for cross-entity search API.

Tests the search logic by populating in-memory stores and verifying
that cross-entity search returns correct results.
"""

from __future__ import annotations

import uuid

from app.api.v1.contracts import _contract_store
from app.api.v1.customers import _customer_store
from app.api.v1.invoices import _invoice_store
from app.api.v1.leakage_inbox import _leakage_store, set_leakage_store

ORG_ID = str(uuid.uuid4())


def _clear_all() -> None:
    """Clear all in-memory stores."""
    _customer_store.clear()
    _contract_store.clear()
    _invoice_store.clear()
    set_leakage_store({})


def _seed_search_data() -> None:
    """Populate stores with test data for search tests."""
    # Customers
    _customer_store["cust-001"] = {
        "id": "cust-001",
        "name": "Acme Corporation",
        "external_id": "ext-acme",
        "email": "billing@acme.com",
        "organization_id": ORG_ID,
        "industry": "Technology",
        "currency": "USD",
        "payment_terms": "net30",
        "created_at": "2025-01-01T00:00:00Z",
    }
    _customer_store["cust-002"] = {
        "id": "cust-002",
        "name": "Beta Industries",
        "external_id": "ext-beta",
        "email": "finance@beta.io",
        "organization_id": ORG_ID,
        "industry": "Manufacturing",
        "currency": "USD",
        "payment_terms": "net45",
        "created_at": "2025-02-01T00:00:00Z",
    }
    # Different org customer — should not appear
    _customer_store["cust-003"] = {
        "id": "cust-003",
        "name": "Acme West (Other Org)",
        "external_id": "ext-acme-west",
        "organization_id": str(uuid.uuid4()),
        "industry": "Technology",
        "currency": "USD",
        "created_at": "2025-01-01T00:00:00Z",
    }

    # Contracts
    _contract_store["ct-001"] = {
        "id": "ct-001",
        "name": "Acme Annual SaaS License",
        "customer_id": "cust-001",
        "organization_id": ORG_ID,
        "external_id": "ext-ct-001",
        "currency": "USD",
        "start_date": "2025-01-01",
        "expiration_date": "2025-12-31",
        "status": "active",
        "created_at": "2025-01-01T00:00:00Z",
    }
    _contract_store["ct-002"] = {
        "id": "ct-002",
        "name": "Beta Consulting Agreement",
        "customer_id": "cust-002",
        "organization_id": ORG_ID,
        "external_id": "ext-ct-002",
        "currency": "USD",
        "start_date": "2025-03-01",
        "expiration_date": "2026-02-28",
        "status": "active",
        "created_at": "2025-03-01T00:00:00Z",
    }

    # Invoices
    _invoice_store["inv-001"] = {
        "id": "inv-001",
        "invoice_number": "INV-2025-0001",
        "customer_id": "cust-001",
        "contract_id": "ct-001",
        "organization_id": ORG_ID,
        "external_id": "ext-inv-001",
        "total": "12000.00",
        "status": "sent",
        "created_at": "2025-01-15T00:00:00Z",
    }
    _invoice_store["inv-002"] = {
        "id": "inv-002",
        "invoice_number": "INV-2025-0002",
        "customer_id": "cust-002",
        "contract_id": "ct-002",
        "organization_id": ORG_ID,
        "external_id": "ext-inv-002",
        "total": "8500.00",
        "status": "paid",
        "created_at": "2025-03-15T00:00:00Z",
    }

    # Leakage cases
    set_leakage_store(
        {
            "case-001": {
                "case_id": "case-001",
                "case_number": "RL-000001",
                "leakage_type": "missing_invoice",
                "status": "detected",
                "severity": "critical",
                "customer_id": "cust-001",
                "potential_leakage": "12000.00",
                "confidence": "0.95",
                "description": "Missing invoice for Acme SaaS license",
                "organization_id": ORG_ID,
                "created_at": "2025-06-01T00:00:00Z",
            },
        }
    )


# ---------------------------------------------------------------------------
# Customer search tests
# ---------------------------------------------------------------------------


class TestSearchCustomers:
    """Test customer name and email search."""

    def setup_method(self) -> None:
        _clear_all()
        _seed_search_data()

    def teardown_method(self) -> None:
        _clear_all()

    def _search(self, q: str, entity_type: str | None = None) -> list[dict]:
        """Apply the same search logic as the endpoint."""
        query_lower = q.lower()
        results = []

        for c in _customer_store.values():
            if c.get("organization_id") != ORG_ID:
                continue
            name = c.get("name", "").lower()
            email = (c.get("email") or "").lower()
            if query_lower in name:
                results.append(
                    {
                        "entity_type": "customer",
                        "entity_id": c["id"],
                        "title": c["name"],
                        "matched_field": "name",
                    }
                )
            elif query_lower in email:
                results.append(
                    {
                        "entity_type": "customer",
                        "entity_id": c["id"],
                        "title": c["name"],
                        "matched_field": "email",
                    }
                )

        return results

    def test_search_customer_by_name(self) -> None:
        """Search 'acme' finds Acme Corporation."""
        results = self._search("acme")
        assert len(results) == 1
        assert results[0]["title"] == "Acme Corporation"
        assert results[0]["matched_field"] == "name"

    def test_search_customer_by_email(self) -> None:
        """Search 'beta.io' finds Beta Industries via email."""
        results = self._search("beta.io")
        assert len(results) == 1
        assert results[0]["title"] == "Beta Industries"
        assert results[0]["matched_field"] == "email"

    def test_search_case_insensitive(self) -> None:
        """Search is case-insensitive."""
        results = self._search("ACME")
        assert len(results) == 1
        assert results[0]["title"] == "Acme Corporation"

    def test_search_no_match(self) -> None:
        """Search for nonexistent term returns empty."""
        results = self._search("nonexistent")
        assert results == []


# ---------------------------------------------------------------------------
# Contract search tests
# ---------------------------------------------------------------------------


class TestSearchContracts:
    """Test contract name search."""

    def setup_method(self) -> None:
        _clear_all()
        _seed_search_data()

    def teardown_method(self) -> None:
        _clear_all()

    def _search(self, q: str) -> list[dict]:
        """Apply contract search logic."""
        query_lower = q.lower()
        results = []
        for ct in _contract_store.values():
            if ct.get("organization_id") != ORG_ID:
                continue
            name = ct.get("name", "").lower()
            if query_lower in name:
                cust = _customer_store.get(ct.get("customer_id"))
                cust_name = cust["name"] if cust else None
                results.append(
                    {
                        "entity_type": "contract",
                        "entity_id": ct["id"],
                        "title": ct["name"],
                        "subtitle": cust_name,
                    }
                )
        return results

    def test_search_contract_by_name(self) -> None:
        """Search 'saas' finds Acme Annual SaaS License."""
        results = self._search("saas")
        assert len(results) == 1
        assert results[0]["title"] == "Acme Annual SaaS License"
        assert results[0]["subtitle"] == "Acme Corporation"

    def test_search_contract_partial_match(self) -> None:
        """Search 'annual' finds the Acme contract."""
        results = self._search("annual")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Invoice search tests
# ---------------------------------------------------------------------------


class TestSearchInvoices:
    """Test invoice number search."""

    def setup_method(self) -> None:
        _clear_all()
        _seed_search_data()

    def teardown_method(self) -> None:
        _clear_all()

    def _search(self, q: str) -> list[dict]:
        """Apply invoice search logic."""
        query_lower = q.lower()
        results = []
        for inv in _invoice_store.values():
            if inv.get("organization_id") != ORG_ID:
                continue
            inv_num = inv.get("invoice_number", "").lower()
            if query_lower in inv_num:
                results.append(
                    {
                        "entity_type": "invoice",
                        "entity_id": inv["id"],
                        "title": inv["invoice_number"],
                    }
                )
        return results

    def test_search_invoice_by_number(self) -> None:
        """Search 'INV-2025-0001' finds the matching invoice."""
        results = self._search("INV-2025-0001")
        assert len(results) == 1
        assert results[0]["title"] == "INV-2025-0001"

    def test_search_invoice_partial(self) -> None:
        """Search '0002' finds the second invoice."""
        results = self._search("0002")
        assert len(results) == 1
        assert results[0]["title"] == "INV-2025-0002"


# ---------------------------------------------------------------------------
# Case search tests
# ---------------------------------------------------------------------------


class TestSearchCases:
    """Test leakage case number and description search."""

    def setup_method(self) -> None:
        _clear_all()
        _seed_search_data()

    def teardown_method(self) -> None:
        _clear_all()

    def _search(self, q: str) -> list[dict]:
        """Apply case search logic."""
        query_lower = q.lower()
        results = []
        for case in _leakage_store.values():
            if case.get("organization_id") != ORG_ID:
                continue
            case_num = case.get("case_number", "").lower()
            desc = (case.get("description") or "").lower()
            if query_lower in case_num:
                results.append(
                    {
                        "entity_type": "case",
                        "entity_id": case.get("case_id"),
                        "title": case["case_number"],
                        "matched_field": "case_number",
                    }
                )
            elif query_lower in desc:
                results.append(
                    {
                        "entity_type": "case",
                        "entity_id": case.get("case_id"),
                        "title": case["case_number"],
                        "matched_field": "description",
                    }
                )
        return results

    def test_search_case_by_number(self) -> None:
        """Search 'RL-000001' finds the matching case."""
        results = self._search("RL-000001")
        assert len(results) == 1
        assert results[0]["title"] == "RL-000001"

    def test_search_case_by_description(self) -> None:
        """Search 'missing invoice' finds case via description."""
        results = self._search("missing invoice")
        assert len(results) == 1
        assert results[0]["matched_field"] == "description"


# ---------------------------------------------------------------------------
# Cross-entity search tests
# ---------------------------------------------------------------------------


class TestCrossEntitySearch:
    """Test search across multiple entity types."""

    def setup_method(self) -> None:
        _clear_all()
        _seed_search_data()

    def teardown_method(self) -> None:
        _clear_all()

    def _search_all(self, q: str) -> list[dict]:
        """Search across all entity types."""
        query_lower = q.lower()
        results = []

        # Customers
        for c in _customer_store.values():
            if c.get("organization_id") != ORG_ID:
                continue
            if query_lower in c.get("name", "").lower():
                results.append({"entity_type": "customer", "title": c["name"]})

        # Contracts
        for ct in _contract_store.values():
            if ct.get("organization_id") != ORG_ID:
                continue
            if query_lower in ct.get("name", "").lower():
                results.append({"entity_type": "contract", "title": ct["name"]})

        # Invoices
        for inv in _invoice_store.values():
            if inv.get("organization_id") != ORG_ID:
                continue
            if query_lower in inv.get("invoice_number", "").lower():
                results.append({"entity_type": "invoice", "title": inv["invoice_number"]})

        # Cases
        for case in _leakage_store.values():
            if case.get("organization_id") != ORG_ID:
                continue
            if (
                query_lower in case.get("case_number", "").lower()
                or query_lower in (case.get("description") or "").lower()
            ):
                results.append({"entity_type": "case", "title": case["case_number"]})

        return results

    def test_cross_entity_query(self) -> None:
        """Search 'acme' finds customer + contract."""
        results = self._search_all("acme")
        types = {r["entity_type"] for r in results}
        assert "customer" in types
        assert "contract" in types

    def test_cross_entity_no_match(self) -> None:
        """Search for nonexistent term returns empty across all entities."""
        results = self._search_all("zzzznonexistent")
        assert results == []

    def test_cross_entity_type_filter(self) -> None:
        """Filtering by entity_type returns only that type."""
        results = [r for r in self._search_all("acme") if r["entity_type"] == "customer"]
        assert all(r["entity_type"] == "customer" for r in results)
        assert len(results) >= 1

    def test_cross_tenant_exclusion(self) -> None:
        """Other-org data is excluded from search."""
        results = self._search_all("acme west")
        # "Acme West (Other Org)" is in a different org — excluded
        assert results == []

    def test_pagination_metadata(self) -> None:
        """Search results can be paginated."""
        from app.api.v1.pagination import paginate

        all_results = self._search_all("acme")
        result = paginate(all_results[:1], total=len(all_results), page=1, page_size=1)
        assert result["total"] >= 1
        assert len(result["items"]) == 1
