"""Tests for SQLAlchemy model definitions.

These tests validate the model structure (column types, enums, constraints)
without requiring a running database. They verify:
- Every tenant-owned table has organization_id
- All monetary columns use NUMERIC(14,2)
- All confidence/ratio columns use NUMERIC(4,3)
- Enums are properly defined
- FK relationships are correctly configured
- Contract deletion does NOT cascade to Invoices
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import Numeric
from sqlalchemy.dialects.postgresql import JSONB

# Import all models to register them with Base.metadata
import app.models  # noqa: F401
from app.db.base import Base
from app.db.enums import (
    ApprovalDecision,
    CaseStatus,
    EvidenceType,
    LeakageType,
    Severity,
)
from app.models.agent import AgentExecution, ToolExecution
from app.models.audit import AuditLog
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.integration import ImportJob
from app.models.invoice import Invoice
from app.models.leakage import Evidence, Investigation, RevenueLeakageCase
from app.models.organization import Organization, User
from app.models.payment import (
    CreditNote,
    Payment,
    Subscription,
)
from app.models.recovery import Approval, RecoveryAction
from app.models.rule import Rule

# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestLeakageTypeEnum:
    def test_has_20_values(self) -> None:
        assert len(LeakageType) == 20

    def test_all_expected_values_present(self) -> None:
        expected = {
            "missing_invoice", "underbilling", "pricing_mismatch",
            "quantity_mismatch", "discount_leakage", "contract_expiration",
            "subscription_renewal", "late_billing", "uncollected_invoice",
            "partial_payment", "reconciliation_failure", "incorrect_credit_note",
            "contract_invoice_conflict", "duplicate_discount",
            "recurring_billing_failure", "usage_billing", "minimum_commitment",
            "sla_credit", "refund_anomaly", "other",
        }
        actual = {e.value for e in LeakageType}
        assert actual == expected

    def test_rejects_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            LeakageType("invalid_leakage_type")


class TestSeverityEnum:
    def test_has_4_values(self) -> None:
        assert len(Severity) == 4

    def test_values(self) -> None:
        assert {e.value for e in Severity} == {"critical", "high", "medium", "low"}


class TestCaseStatusEnum:
    def test_has_12_values(self) -> None:
        assert len(CaseStatus) == 12

    def test_values(self) -> None:
        expected = {
            "detected", "investigating", "pending_review", "approved",
            "rejected", "action_pending", "action_completed", "verified",
            "recovered", "false_positive", "legitimate_exception", "closed",
        }
        assert {e.value for e in CaseStatus} == expected


class TestEvidenceTypeEnum:
    def test_has_values(self) -> None:
        assert len(EvidenceType) >= 8


class TestApprovalDecisionEnum:
    def test_has_3_values(self) -> None:
        assert len(ApprovalDecision) == 3

    def test_values(self) -> None:
        expected = {"approved", "rejected", "needs_more_information"}
        assert {e.value for e in ApprovalDecision} == expected


# ---------------------------------------------------------------------------
# Schema inspection tests — validate column types via model metadata
# (No SQLite create_all needed — we inspect the metadata objects directly)
# ---------------------------------------------------------------------------

# Tables that should exist
EXPECTED_TABLES = {
    "organizations", "users", "roles", "permissions", "role_permissions",
    "customers", "customer_contacts",
    "contracts", "contract_lines",
    "projects", "products", "services",
    "invoices", "invoice_lines",
    "payments", "payment_allocations", "subscriptions", "credit_notes",
    "revenue_leakage_cases", "evidence", "investigations",
    "agent_executions", "tool_executions",
    "recovery_actions", "recovery_results", "approvals",
    "rules", "rule_versions",
    "integrations", "data_sources", "import_jobs",
    "audit_logs",
}


class TestAllTablesExist:
    def test_all_expected_tables_created(self) -> None:
        actual = set(Base.metadata.tables.keys())
        missing = EXPECTED_TABLES - actual
        assert not missing, f"Missing tables: {missing}"


# Tables that MUST have organization_id (tenant-owned)
TENANT_TABLES = {
    "users", "roles",
    "customers", "customer_contacts",
    "contracts", "contract_lines",
    "projects", "products", "services",
    "invoices", "invoice_lines",
    "payments", "payment_allocations", "subscriptions", "credit_notes",
    "revenue_leakage_cases", "evidence", "investigations",
    "agent_executions", "tool_executions",
    "recovery_actions", "recovery_results", "approvals",
    "rules", "rule_versions",
    "integrations", "data_sources", "import_jobs",
    "audit_logs",
}


class TestTenantIsolation:
    def test_all_tenant_tables_have_organization_id(self) -> None:
        missing_org_id = []
        for table_name in TENANT_TABLES:
            table = Base.metadata.tables[table_name]
            columns = {col.name for col in table.columns}
            if "organization_id" not in columns:
                missing_org_id.append(table_name)
        assert not missing_org_id, f"Tables missing organization_id: {missing_org_id}"


# Tables with monetary NUMERIC(14,2) columns
MONEY_TABLES = {
    "contracts": ["total_value", "minimum_commitment"],
    "contract_lines": ["unit_price", "total"],
    "invoices": ["subtotal", "tax_amount", "total", "outstanding_balance"],
    "invoice_lines": ["unit_price", "total"],
    "payments": ["amount"],
    "payment_allocations": ["amount"],
    "subscriptions": ["unit_price"],
    "credit_notes": ["amount"],
    "revenue_leakage_cases": [
        "expected_amount", "actual_amount", "potential_leakage", "recoverable_amount",
    ],
    "recovery_results": ["recovered_amount"],
}


class TestMonetaryColumns:
    def test_money_columns_are_numeric(self) -> None:
        for table_name, columns in MONEY_TABLES.items():
            for col_name in columns:
                table = Base.metadata.tables[table_name]
                model_col = getattr(table.c, col_name)
                assert isinstance(model_col.type, Numeric), (
                    f"{table_name}.{col_name} should be NUMERIC(14,2), "
                    f"got {type(model_col.type)}"
                )
                assert model_col.type.precision == 14, (
                    f"{table_name}.{col_name} precision should be 14"
                )
                assert model_col.type.scale == 2, (
                    f"{table_name}.{col_name} scale should be 2"
                )


# Confidence/ratio columns use NUMERIC(4,3)
CONFIDENCE_TABLES = {
    "revenue_leakage_cases": ["confidence"],
    "tool_executions": ["confidence"],
    "contracts": ["discount_cap_pct"],
}


class TestConfidenceColumns:
    def test_confidence_columns_are_numeric_4_3(self) -> None:
        for table_name, columns in CONFIDENCE_TABLES.items():
            for col_name in columns:
                table = Base.metadata.tables[table_name]
                model_col = getattr(table.c, col_name)
                assert isinstance(model_col.type, Numeric), (
                    f"{table_name}.{col_name} should be NUMERIC(4,3), "
                    f"got {type(model_col.type)}"
                )
                assert model_col.type.precision == 4
                assert model_col.type.scale == 3


# ---------------------------------------------------------------------------
# Relationship tests
# ---------------------------------------------------------------------------

class TestRelationships:
    def test_contract_does_not_cascade_delete_invoices(self) -> None:
        """Deleting a Contract must NOT cascade-delete Invoices.

        Revenue history must be preservable. Invoices carry their own
        contract_id FK with no cascade rule.
        """
        invoice_table = Invoice.__table__
        for col in invoice_table.columns:
            for fk in col.foreign_keys:
                if fk.column.table.name == "contracts":
                    assert fk.ondelete != "CASCADE", (
                        "Invoice.contract_id must not cascade on Contract delete"
                    )

    def test_revenue_leakage_case_has_case_number(self) -> None:
        """RevenueLeakageCase must have a human-readable case_number."""
        columns = {c.name for c in RevenueLeakageCase.__table__.columns}
        assert "case_number" in columns

    def test_evidence_has_jsonb_snapshot(self) -> None:
        """Evidence.snapshot must be JSONB."""
        snapshot_col = Evidence.__table__.c.snapshot
        assert isinstance(snapshot_col.type, JSONB)

    def test_agent_execution_has_agent_name(self) -> None:
        columns = {c.name for c in AgentExecution.__table__.columns}
        assert "agent_name" in columns

    def test_tool_execution_references_agent_execution(self) -> None:
        fk_cols = {
            c.name for c in ToolExecution.__table__.columns
            if c.foreign_keys
        }
        assert "agent_execution_id" in fk_cols

    def test_all_tables_have_pk(self) -> None:
        """Every table must have a primary key."""
        for table_name in EXPECTED_TABLES:
            table = Base.metadata.tables[table_name]
            assert table.primary_key, f"{table_name} has no primary key"


# ---------------------------------------------------------------------------
# Model instantiation tests (in-memory, no DB required)
# Note: server_default values are only applied on DB insert, not on
# Python instantiation. Tests check that models CAN be created, not
# that defaults are applied.
# ---------------------------------------------------------------------------

class TestModelInstantiation:
    """Verify that every model can be instantiated with valid data."""

    def _make_uuid(self) -> uuid.UUID:
        return uuid.uuid4()

    def test_organization(self) -> None:
        org = Organization(name="Acme", slug="acme")
        assert org.name == "Acme"

    def test_user(self) -> None:
        user = User(
            organization_id=self._make_uuid(),
            email="test@acme.com",
            hashed_password="hashed",
        )
        assert user.email == "test@acme.com"

    def test_customer(self) -> None:
        cust = Customer(
            organization_id=self._make_uuid(),
            name="Acme Corp",
        )
        assert cust.name == "Acme Corp"

    def test_contract(self) -> None:
        from datetime import date
        contract = Contract(
            organization_id=self._make_uuid(),
            customer_id=self._make_uuid(),
            contract_number="C-001",
            name="Support Agreement",
            start_date=date(2026, 1, 1),
        )
        assert contract.total_value is None  # nullable

    def test_invoice(self) -> None:
        inv = Invoice(
            organization_id=self._make_uuid(),
            customer_id=self._make_uuid(),
            invoice_number="INV-001",
        )
        # server_default applies on DB insert; Python object has None
        assert inv.invoice_number == "INV-001"

    def test_revenue_leakage_case(self) -> None:
        case = RevenueLeakageCase(
            organization_id=self._make_uuid(),
            case_number="RL-000001",
            leakage_type=LeakageType.missing_invoice.value,
            status=CaseStatus.detected.value,
        )
        assert case.case_number == "RL-000001"

    def test_evidence(self) -> None:
        ev = Evidence(
            organization_id=self._make_uuid(),
            case_id=self._make_uuid(),
            evidence_type=EvidenceType.contract_snapshot.value,
            source_table="contracts",
            source_id=self._make_uuid(),
            snapshot={"key": "value"},
        )
        assert ev.snapshot == {"key": "value"}

    def test_investigation(self) -> None:
        inv = Investigation(
            organization_id=self._make_uuid(),
            case_id=self._make_uuid(),
            classification="confirmed",
            explanation="Contract shows discrepancy",
            evidence_ids=[],
        )
        assert inv.classification == "confirmed"

    def test_recovery_action(self) -> None:
        ra = RecoveryAction(
            organization_id=self._make_uuid(),
            case_id=self._make_uuid(),
            action_type="create_invoice_draft",
        )
        assert ra.action_type == "create_invoice_draft"

    def test_approval(self) -> None:
        appr = Approval(
            organization_id=self._make_uuid(),
            decision=ApprovalDecision.approved.value,
            decided_by=self._make_uuid(),
        )
        assert appr.decision == "approved"

    def test_rule(self) -> None:
        rule = Rule(
            organization_id=self._make_uuid(),
            name="Missing Invoice",
            leakage_type=LeakageType.missing_invoice.value,
        )
        assert rule.name == "Missing Invoice"

    def test_audit_log(self) -> None:
        log = AuditLog(
            organization_id=self._make_uuid(),
            event_type="user.login",
            actor_email="user@acme.com",
        )
        assert log.event_type == "user.login"

    def test_import_job(self) -> None:
        job = ImportJob(
            organization_id=self._make_uuid(),
            target_entity="customers",
            source="csv",
        )
        assert job.target_entity == "customers"

    def test_credit_note(self) -> None:
        cn = CreditNote(
            organization_id=self._make_uuid(),
            customer_id=self._make_uuid(),
            credit_note_number="CN-001",
            amount=Decimal("500.00"),
        )
        assert cn.amount == Decimal("500.00")

    def test_payment(self) -> None:
        pay = Payment(
            organization_id=self._make_uuid(),
            customer_id=self._make_uuid(),
            amount=Decimal("1000.00"),
            payment_date="2026-01-15",
        )
        assert pay.amount == Decimal("1000.00")

    def test_subscription(self) -> None:
        sub = Subscription(
            organization_id=self._make_uuid(),
            customer_id=self._make_uuid(),
            name="Monthly SaaS",
            billing_frequency="monthly",
            unit_price=Decimal("99.00"),
            start_date="2026-01-01",
        )
        assert sub.billing_frequency == "monthly"
