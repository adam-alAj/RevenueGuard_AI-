"""Case state machine — single source of truth for all status transitions.

Every transition is explicit in the TRANSITION_TABLE. Any transition
not in the table is rejected with a clear error message.

12 statuses:
  detected → investigating → pending_review → approved → action_pending
                                                         → action_completed
                                                         → verified
                                                         → recovered
                                                    → rejected
                                                    → closed
  Also: false_positive, legitimate_exception (terminal states)

Legal transitions (from → to):
  detected          → investigating, closed
  investigating     → pending_review, closed
  pending_review    → approved, rejected, closed
  approved          → action_pending, closed
  action_pending    → action_completed, closed
  action_completed  → verified, recovered, closed
  verified          → closed
  recovered         → closed
  rejected          → closed
  false_positive    → closed (terminal — already closed)
  legitimate_exception → closed (terminal — already closed)
  closed            → (none — terminal state)
"""

from __future__ import annotations

# The single source of truth: which transitions are legal
TRANSITION_TABLE: dict[str, set[str]] = {
    "detected": {"investigating", "closed"},
    "investigating": {"pending_review", "closed"},
    "pending_review": {"approved", "rejected", "investigating", "closed"},
    "approved": {"action_pending", "closed"},
    "action_pending": {"action_completed", "closed"},
    "action_completed": {"verified", "recovered", "closed"},
    "verified": {"closed"},
    "recovered": {"closed"},
    "rejected": {"closed"},
    "false_positive": {"closed"},
    "legitimate_exception": {"closed"},
    "closed": set(),  # terminal — no transitions out
}

# All valid statuses
ALL_STATUSES = set(TRANSITION_TABLE.keys())

# Terminal states (no transitions out except self-closure)
TERMINAL_STATUSES = {"closed", "false_positive", "legitimate_exception"}


class InvalidTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, current_status: str, target_status: str) -> None:
        self.current_status = current_status
        self.target_status = target_status
        allowed = TRANSITION_TABLE.get(current_status, set())
        super().__init__(
            f"Invalid transition: {current_status} → {target_status}. "
            f"Allowed transitions from '{current_status}': "
            f"{sorted(allowed) if allowed else '(none — terminal state)'}"
        )


def validate_transition(current_status: str, target_status: str) -> None:
    """Validate that a status transition is legal.

    Args:
        current_status: The current status of the case.
        target_status: The desired target status.

    Raises:
        InvalidTransitionError: If the transition is not in the table.
        ValueError: If either status is not a valid status.
    """
    if current_status not in ALL_STATUSES:
        raise ValueError(
            f"Unknown current status: '{current_status}'. "
            f"Valid statuses: {sorted(ALL_STATUSES)}"
        )
    if target_status not in ALL_STATUSES:
        raise ValueError(
            f"Unknown target status: '{target_status}'. "
            f"Valid statuses: {sorted(ALL_STATUSES)}"
        )

    allowed = TRANSITION_TABLE.get(current_status, set())
    if target_status not in allowed:
        raise InvalidTransitionError(current_status, target_status)


def get_allowed_transitions(current_status: str) -> set[str]:
    """Get the set of allowed target statuses from a given status.

    Args:
        current_status: The current status.

    Returns:
        Set of allowed target statuses.

    Raises:
        ValueError: If the status is not valid.
    """
    if current_status not in ALL_STATUSES:
        raise ValueError(
            f"Unknown status: '{current_status}'. "
            f"Valid statuses: {sorted(ALL_STATUSES)}"
        )
    return set(TRANSITION_TABLE.get(current_status, set()))


def is_terminal(status: str) -> bool:
    """Check if a status is terminal (no transitions out).

    Args:
        status: The status to check.

    Returns:
        True if the status is terminal.
    """
    return status in TERMINAL_STATUSES


def can_transition_to(current_status: str, target_status: str) -> bool:
    """Check if a transition is allowed without raising.

    Args:
        current_status: The current status.
        target_status: The desired target status.

    Returns:
        True if the transition is allowed.
    """
    try:
        validate_transition(current_status, target_status)
        return True
    except (InvalidTransitionError, ValueError):
        return False
