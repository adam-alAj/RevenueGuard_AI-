"""Enums used across the RevenueGuard AI domain model."""

from __future__ import annotations

import enum


class LeakageType(str, enum.Enum):
    """The 20 types of revenue leakage the platform detects."""

    missing_invoice = "missing_invoice"
    underbilling = "underbilling"
    pricing_mismatch = "pricing_mismatch"
    quantity_mismatch = "quantity_mismatch"
    discount_leakage = "discount_leakage"
    contract_expiration = "contract_expiration"
    subscription_renewal = "subscription_renewal"
    late_billing = "late_billing"
    uncollected_invoice = "uncollected_invoice"
    partial_payment = "partial_payment"
    reconciliation_failure = "reconciliation_failure"
    incorrect_credit_note = "incorrect_credit_note"
    contract_invoice_conflict = "contract_invoice_conflict"
    duplicate_discount = "duplicate_discount"
    recurring_billing_failure = "recurring_billing_failure"
    usage_billing = "usage_billing"
    minimum_commitment = "minimum_commitment"
    sla_credit = "sla_credit"
    refund_anomaly = "refund_anomaly"
    other = "other"


class Severity(str, enum.Enum):
    """Severity level assigned to a revenue leakage case."""

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class CaseStatus(str, enum.Enum):
    """Lifecycle status of a RevenueLeakageCase."""

    detected = "detected"
    investigating = "investigating"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    action_pending = "action_pending"
    action_completed = "action_completed"
    verified = "verified"
    recovered = "recovered"
    false_positive = "false_positive"
    legitimate_exception = "legitimate_exception"
    closed = "closed"


class EvidenceType(str, enum.Enum):
    """Type of evidence attached to a leakage case."""

    contract_snapshot = "contract_snapshot"
    invoice_snapshot = "invoice_snapshot"
    payment_snapshot = "payment_snapshot"
    project_snapshot = "project_snapshot"
    operational_record = "operational_record"
    email_correspondence = "email_correspondence"
    agent_analysis = "agent_analysis"
    manual_note = "manual_note"
    system_generated = "system_generated"


class ApprovalDecision(str, enum.Enum):
    """Decision recorded on an approval action."""

    approved = "approved"
    rejected = "rejected"
    needs_more_information = "needs_more_information"
