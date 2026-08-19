"""Deterministic templates for recovery action drafts.

Every template is fed ONLY by verified financial-impact numbers from
Phase 9's deterministic calculator — never LLM free-generation of
dollar amounts. The template system ensures:

1. Dollar figures come from Phase 9's Decimal-backed calculations
2. All text is interpolated from verified case facts
3. No template produces a customer-facing artifact without human review
4. Each action type has a specific draft format

Action types and their draft formats:
- create_invoice_draft → structured draft invoice JSON
- send_payment_reminder → templated reminder text
- All others → internal task record
"""

from __future__ import annotations

from decimal import Decimal

from app.scoring.financial_impact import FinancialImpactCalculator

# --- Invoice Draft Template ---


def render_invoice_draft(
    customer_name: str,
    case_number: str,
    leakage_type: str,
    expected_amount: Decimal,
    actual_amount: Decimal,
    potential_leakage: Decimal,
    currency: str = "USD",
) -> dict:
    """Render a structured draft invoice for human review.

    All monetary values come from Phase 9's deterministic calculator.
    The draft is a JSONB-serializable dict stored in RecoveryAction.draft_content.

    Args:
        customer_name: Name of the customer.
        case_number: The case reference number (e.g., RL-000123).
        leakage_type: Type of leakage detected.
        expected_amount: What should have been billed (from Phase 9).
        actual_amount: What was actually billed (from Phase 9).
        potential_leakage: The difference (from Phase 9).
        currency: ISO 4217 currency code.

    Returns:
        Structured draft invoice dict.
    """
    return {
        "type": "invoice_draft",
        "draft_status": "pending_approval",
        "customer": {
            "name": customer_name,
        },
        "invoice": {
            "reference": f"DRAFT-{case_number}",
            "description": (
                f"Corrective invoice for {leakage_type.replace('_', ' ')} "
                f"detected in case {case_number}"
            ),
            "line_items": [
                {
                    "description": (
                        f"Revenue correction: {leakage_type.replace('_', ' ')} "
                        f"(expected ${expected_amount:.2f} - billed ${actual_amount:.2f})"
                    ),
                    "quantity": 1,
                    "unit_price": str(potential_leakage),
                    "amount": str(potential_leakage),
                }
            ],
            "subtotal": str(potential_leakage),
            "currency": currency,
            "total": str(potential_leakage),
            "notes": (
                f"This draft invoice was generated for case {case_number}. "
                f"Expected billing: ${expected_amount:.2f}. "
                f"Actual billing: ${actual_amount:.2f}. "
                f"Correction amount: ${potential_leakage:.2f}. "
                f"Requires manual review before sending."
            ),
        },
        "source_of_truth": {
            "expected_amount": str(expected_amount),
            "actual_amount": str(actual_amount),
            "potential_leakage": str(potential_leakage),
            "calculator": "Phase 9 FinancialImpactCalculator",
        },
    }


# --- Payment Reminder Template ---


def render_payment_reminder(
    customer_name: str,
    case_number: str,
    leakage_type: str,
    expected_amount: Decimal,
    actual_amount: Decimal,
    potential_leakage: Decimal,
    currency: str = "USD",
) -> dict:
    """Render a templated payment reminder for human review.

    All monetary values come from Phase 9's deterministic calculator.

    Args:
        customer_name: Name of the customer.
        case_number: The case reference number.
        leakage_type: Type of leakage detected.
        expected_amount: What should have been billed.
        actual_amount: What was actually billed.
        potential_leakage: The difference.
        currency: ISO 4217 currency code.

    Returns:
        Structured reminder draft dict.
    """
    formatted_amount = FinancialImpactCalculator.format_currency(potential_leakage, currency)
    reminder_text = (
        f"Dear {customer_name},\n\n"
        f"Our records indicate a billing discrepancy identified in case {case_number}. "
        f"The expected amount was ${expected_amount:.2f}, but the invoiced amount was "
        f"${actual_amount:.2f}. The outstanding balance is {formatted_amount}.\n\n"
        f"Please review this discrepancy and arrange payment at your earliest convenience.\n\n"
        f"Reference: {case_number}\n"
        f"Leakage type: {leakage_type.replace('_', ' ').title()}\n\n"
        f"This reminder was generated from verified financial records and requires "
        f"manual review before sending."
    )

    return {
        "type": "payment_reminder",
        "draft_status": "pending_approval",
        "customer": {
            "name": customer_name,
        },
        "reminder": {
            "subject": (f"Payment Reminder — Billing Discrepancy {case_number}"),
            "body": reminder_text,
            "amount_due": str(potential_leakage),
            "currency": currency,
        },
        "source_of_truth": {
            "expected_amount": str(expected_amount),
            "actual_amount": str(actual_amount),
            "potential_leakage": str(potential_leakage),
            "calculator": "Phase 9 FinancialImpactCalculator",
        },
    }


# --- Internal Task Template ---


def render_internal_task(
    action_type: str,
    case_number: str,
    leakage_type: str,
    expected_amount: Decimal,
    actual_amount: Decimal,
    potential_leakage: Decimal,
    rationale: str = "",
    currency: str = "USD",
) -> dict:
    """Render an internal task record for non-customer-facing actions.

    Used for: request_internal_investigation, correct_pricing,
    contact_account_manager, renew_contract, reconcile_payment,
    issue_correction, escalate_to_finance_manager.

    Args:
        action_type: The specific action type.
        case_number: The case reference number.
        leakage_type: Type of leakage detected.
        expected_amount: What should have been billed.
        actual_amount: What was actually billed.
        potential_leakage: The difference.
        rationale: Why this action was recommended.
        currency: ISO 4217 currency code.

    Returns:
        Structured internal task dict.
    """
    formatted_amount = FinancialImpactCalculator.format_currency(potential_leakage, currency)

    task_titles = {
        "request_internal_investigation": "Internal Investigation Required",
        "correct_pricing": "Pricing Correction Needed",
        "contact_account_manager": "Account Manager Follow-Up Required",
        "renew_contract": "Contract Renewal Action Required",
        "reconcile_payment": "Payment Reconciliation Required",
        "issue_correction": "Credit/Debit Correction Required",
        "escalate_to_finance_manager": "Escalation to Finance Manager",
    }

    task_descriptions = {
        "request_internal_investigation": (
            f"Case {case_number} requires deeper internal investigation. "
            f"The detected {leakage_type.replace('_', ' ')} of {formatted_amount} "
            f"(expected ${expected_amount:.2f} vs actual ${actual_amount:.2f}) "
            f"needs additional review before further action."
        ),
        "correct_pricing": (
            f"Case {case_number} identified a pricing error. "
            f"The correct price should be ${expected_amount:.2f}, "
            f"but ${actual_amount:.2f} was billed. "
            f"Correction needed: {formatted_amount}."
        ),
        "contact_account_manager": (
            f"Case {case_number} requires account manager follow-up. "
            f"A {leakage_type.replace('_', ' ')} of {formatted_amount} was detected. "
            f"The account manager should contact the customer to resolve."
        ),
        "renew_contract": (
            f"Case {case_number} involves a contract expiration. "
            f"Potential revenue at risk: {formatted_amount}. "
            f"Contract renewal should be initiated."
        ),
        "reconcile_payment": (
            f"Case {case_number} has a payment discrepancy. "
            f"Expected ${expected_amount:.2f}, received ${actual_amount:.2f}. "
            f"Payment reconciliation required for {formatted_amount}."
        ),
        "issue_correction": (
            f"Case {case_number} requires a credit or debit correction. "
            f"The correction amount is {formatted_amount} "
            f"(${expected_amount:.2f} expected vs ${actual_amount:.2f} actual)."
        ),
        "escalate_to_finance_manager": (
            f"Case {case_number} has been escalated to the finance manager. "
            f"The {leakage_type.replace('_', ' ')} of {formatted_amount} "
            f"requires senior financial review."
        ),
    }

    return {
        "type": "internal_task",
        "draft_status": "pending_approval",
        "task": {
            "title": task_titles.get(action_type, f"Action Required: {action_type}"),
            "description": task_descriptions.get(
                action_type,
                f"Action {action_type} required for case {case_number}. "
                f"Amount: {formatted_amount}.",
            ),
            "priority": "high" if potential_leakage >= Decimal("5000") else "medium",
            "amount_at_risk": str(potential_leakage),
            "currency": currency,
        },
        "source_of_truth": {
            "expected_amount": str(expected_amount),
            "actual_amount": str(actual_amount),
            "potential_leakage": str(potential_leakage),
            "calculator": "Phase 9 FinancialImpactCalculator",
        },
    }


# --- Template Router ---


def render_draft(
    action_type: str,
    customer_name: str,
    case_number: str,
    leakage_type: str,
    expected_amount: Decimal,
    actual_amount: Decimal,
    potential_leakage: Decimal,
    rationale: str = "",
    currency: str = "USD",
) -> dict:
    """Route to the correct template based on action type.

    Args:
        action_type: The recovery action type.
        customer_name: Customer name.
        case_number: Case reference number.
        leakage_type: Type of leakage.
        expected_amount: Expected amount (from Phase 9).
        actual_amount: Actual amount (from Phase 9).
        potential_leakage: Leakage amount (from Phase 9).
        rationale: Why this action was recommended.
        currency: ISO 4217 currency code.

    Returns:
        Draft content dict.
    """
    if action_type == "create_invoice_draft":
        return render_invoice_draft(
            customer_name=customer_name,
            case_number=case_number,
            leakage_type=leakage_type,
            expected_amount=expected_amount,
            actual_amount=actual_amount,
            potential_leakage=potential_leakage,
            currency=currency,
        )
    elif action_type == "send_payment_reminder":
        return render_payment_reminder(
            customer_name=customer_name,
            case_number=case_number,
            leakage_type=leakage_type,
            expected_amount=expected_amount,
            actual_amount=actual_amount,
            potential_leakage=potential_leakage,
            currency=currency,
        )
    else:
        return render_internal_task(
            action_type=action_type,
            case_number=case_number,
            leakage_type=leakage_type,
            expected_amount=expected_amount,
            actual_amount=actual_amount,
            potential_leakage=potential_leakage,
            rationale=rationale,
            currency=currency,
        )
