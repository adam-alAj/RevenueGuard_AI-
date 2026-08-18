"""SQLAlchemy models for RevenueGuard AI.

Every tenant-owned model inherits TenantMixin (ADR-003) and carries a
non-nullable, indexed organization_id column.

All monetary columns use NUMERIC(14,2). Confidence/ratio columns use
NUMERIC(4,3).
"""

from app.models.agent import AgentExecution, ToolExecution
from app.models.audit import AuditLog
from app.models.contract import Contract, ContractLine
from app.models.customer import Customer, CustomerContact
from app.models.integration import DataSource, ImportJob, Integration
from app.models.invoice import Invoice, InvoiceLine
from app.models.leakage import Evidence, Investigation, RevenueLeakageCase
from app.models.organization import Organization, Permission, Role, User
from app.models.payment import (
    CreditNote,
    Payment,
    PaymentAllocation,
    Subscription,
)
from app.models.project import Product, Project, Service
from app.models.recovery import Approval, RecoveryAction, RecoveryResult
from app.models.rule import Rule, RuleVersion

__all__ = [
    "AgentExecution",
    "Approval",
    "AuditLog",
    "Contract",
    "ContractLine",
    "CreditNote",
    "Customer",
    "CustomerContact",
    "DataSource",
    "Evidence",
    "ImportJob",
    "Integration",
    "Investigation",
    "Invoice",
    "InvoiceLine",
    "Organization",
    "Payment",
    "PaymentAllocation",
    "Permission",
    "Product",
    "Project",
    "RecoveryAction",
    "RecoveryResult",
    "RevenueLeakageCase",
    "Role",
    "Rule",
    "RuleVersion",
    "Service",
    "Subscription",
    "ToolExecution",
    "User",
]
