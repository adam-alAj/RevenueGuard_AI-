"""Deterministic Revenue Leakage Rules Engine.

Runs all 6 MVP rules against normalized data and emits
RevenueLeakageCase candidates with status="detected".

No LLM involvement. All monetary comparisons use Decimal.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract, ContractLine
from app.models.invoice import Invoice, InvoiceLine
from app.models.leakage import RevenueLeakageCase
from app.models.payment import CreditNote, Payment
from app.models.project import Project
from app.models.rule import Rule, RuleVersion
from app.rules.base import BaseRule, RuleContext
from app.rules.contract_expiration import ContractExpirationRule
from app.rules.missing_invoice import MissingInvoiceRule
from app.rules.overdue_invoice import OverdueInvoiceRule
from app.rules.partial_payment import PartialPaymentRule
from app.rules.pricing_mismatch import PricingMismatchRule
from app.rules.underbilling import UnderbillingRule

# Registry of all rules
ALL_RULES: list[BaseRule] = [
    MissingInvoiceRule(),
    UnderbillingRule(),
    PricingMismatchRule(),
    OverdueInvoiceRule(),
    PartialPaymentRule(),
    ContractExpirationRule(),
]

# Map leakage_type to rule instance
RULE_MAP: dict[str, BaseRule] = {r.leakage_type: r for r in ALL_RULES}


async def _load_context(
    db: AsyncSession,
    org_id: uuid.UUID,
    rule_version: RuleVersion,
    today: date | None = None,
) -> RuleContext:
    """Load all data needed by rules into a RuleContext."""
    if today is None:
        today = date.today()

    # Load projects
    result = await db.execute(select(Project).where(Project.organization_id == org_id))
    projects = [
        {
            "id": p.id,
            "name": p.name,
            "status": p.status,
            "customer_id": p.customer_id,
            "contract_id": p.contract_id,
            "is_billable": p.is_billable,
            "end_date": p.end_date,
            "start_date": p.start_date,
        }
        for p in result.scalars().all()
    ]

    # Load contracts
    result = await db.execute(select(Contract).where(Contract.organization_id == org_id))
    contracts = [
        {
            "id": c.id,
            "name": c.name,
            "customer_id": c.customer_id,
            "start_date": c.start_date,
            "end_date": c.end_date,
            "expiration_date": c.expiration_date,
            "total_value": c.total_value,
            "billing_frequency": c.billing_frequency,
        }
        for c in result.scalars().all()
    ]

    # Load contract lines
    result = await db.execute(select(ContractLine).where(ContractLine.organization_id == org_id))
    contract_lines = [
        {
            "id": cl.id,
            "contract_id": cl.contract_id,
            "description": cl.description,
            "quantity": cl.quantity,
            "unit_price": cl.unit_price,
            "total": cl.total,
        }
        for cl in result.scalars().all()
    ]

    # Load invoices
    result = await db.execute(select(Invoice).where(Invoice.organization_id == org_id))
    invoices = [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "customer_id": inv.customer_id,
            "contract_id": inv.contract_id,
            "project_id": inv.project_id,
            "total": inv.total,
            "outstanding_balance": inv.outstanding_balance,
            "due_date": inv.due_date,
            "issued_date": inv.issued_date,
        }
        for inv in result.scalars().all()
    ]

    # Load invoice lines
    result = await db.execute(select(InvoiceLine).where(InvoiceLine.organization_id == org_id))
    invoice_lines = [
        {
            "id": il.id,
            "invoice_id": il.invoice_id,
            "description": il.description,
            "quantity": il.quantity,
            "unit_price": il.unit_price,
            "total": il.total,
        }
        for il in result.scalars().all()
    ]

    # Load payments
    result = await db.execute(select(Payment).where(Payment.organization_id == org_id))
    payments = [
        {
            "id": pay.id,
            "customer_id": pay.customer_id,
            "amount": pay.amount,
            "payment_date": pay.payment_date,
        }
        for pay in result.scalars().all()
    ]

    # Load credit notes
    result = await db.execute(select(CreditNote).where(CreditNote.organization_id == org_id))
    credit_notes = [
        {
            "id": cn.id,
            "invoice_id": cn.invoice_id,
            "amount": cn.amount,
            "customer_id": cn.customer_id,
        }
        for cn in result.scalars().all()
    ]

    return RuleContext(
        organization_id=org_id,
        rule_version_id=rule_version.id,
        parameters=rule_version.parameters or {},
        today=today,
        projects=projects,
        contracts=contracts,
        contract_lines=contract_lines,
        invoices=invoices,
        invoice_lines=invoice_lines,
        payments=payments,
        credit_notes=credit_notes,
    )


# Case number counter (per-org, in-memory for MVP)
_case_counters: dict[str, int] = {}


def _next_case_number(org_id: uuid.UUID) -> str:
    """Generate the next case number (RL-000001 format)."""
    key = str(org_id)
    _case_counters[key] = _case_counters.get(key, 0) + 1
    return f"RL-{_case_counters[key]:06d}"


async def run_rules(
    db: AsyncSession,
    org_id: uuid.UUID,
    rule_types: list[str] | None = None,
    today: date | None = None,
) -> list[RevenueLeakageCase]:
    """Run all (or selected) rules and persist findings as RevenueLeakageCases.

    Returns the list of created cases.
    """
    # Find active rules for this org
    result = await db.execute(
        select(Rule)
        .join(RuleVersion, RuleVersion.rule_id == Rule.id)
        .where(
            Rule.organization_id == org_id,
            Rule.is_active == True,  # noqa: E712
            RuleVersion.is_active == True,  # noqa: E712
        )
        .distinct()
    )
    rules = result.scalars().all()

    all_cases: list[RevenueLeakageCase] = []

    for rule in rules:
        if rule_types and rule.leakage_type not in rule_types:
            continue

        rule_impl = RULE_MAP.get(rule.leakage_type)
        if rule_impl is None:
            continue

        # Get the latest active version
        version_result = await db.execute(
            select(RuleVersion)
            .where(
                RuleVersion.rule_id == rule.id,
                RuleVersion.is_active == True,  # noqa: E712
            )
            .order_by(RuleVersion.version.desc())
            .limit(1)
        )
        version = version_result.scalar_one_or_none()
        if version is None:
            continue

        # Load context and evaluate
        execution_id = str(uuid.uuid4())
        ctx = await _load_context(db, org_id, version, today)
        findings = rule_impl.evaluate(ctx)

        # Persist findings as RevenueLeakageCases
        for finding in findings:
            correlation_id = finding.correlation_id or execution_id
            case = RevenueLeakageCase(
                organization_id=org_id,
                case_number=_next_case_number(org_id),
                leakage_type=finding.leakage_type,
                status="detected",
                customer_id=finding.customer_id,
                contract_id=finding.contract_id,
                invoice_id=finding.invoice_id,
                project_id=finding.project_id,
                expected_amount=finding.expected_amount,
                actual_amount=finding.actual_amount,
                potential_leakage=finding.potential_leakage,
                recoverable_amount=finding.potential_leakage,
                description=finding.description,
                rule_version_id=version.id,
                correlation_id=correlation_id,
            )
            db.add(case)
            all_cases.append(case)

    await db.flush()
    return all_cases
