"""Tests for the case state machine — legal and illegal transitions.

Verifies:
- All 12 statuses are recognized
- All legal transitions work
- All illegal transitions are rejected with clear errors
- Terminal states have no transitions out
- Edge cases (unknown status, self-transitions)
"""

from __future__ import annotations

import pytest

from app.services.case_state_machine import (
    ALL_STATUSES,
    TERMINAL_STATUSES,
    TRANSITION_TABLE,
    InvalidTransitionError,
    can_transition_to,
    get_allowed_transitions,
    is_terminal,
    validate_transition,
)


class TestAllStatuses:
    """Verify all 12 statuses are recognized."""

    def test_12_statuses_defined(self) -> None:
        """All 12 statuses are in the transition table."""
        assert len(ALL_STATUSES) == 12

    def test_expected_statuses_present(self) -> None:
        """All expected status names are present."""
        expected = {
            "detected",
            "investigating",
            "pending_review",
            "approved",
            "rejected",
            "action_pending",
            "action_completed",
            "verified",
            "recovered",
            "false_positive",
            "legitimate_exception",
            "closed",
        }
        assert expected == ALL_STATUSES


class TestLegalTransitions:
    """Test all legal transitions."""

    def test_detected_to_investigating(self) -> None:
        """detected → investigating is legal."""
        validate_transition("detected", "investigating")

    def test_detected_to_closed(self) -> None:
        """detected → closed is legal."""
        validate_transition("detected", "closed")

    def test_investigating_to_pending_review(self) -> None:
        """investigating → pending_review is legal."""
        validate_transition("investigating", "pending_review")

    def test_investigating_to_closed(self) -> None:
        """investigating → closed is legal."""
        validate_transition("investigating", "closed")

    def test_pending_review_to_approved(self) -> None:
        """pending_review → approved is legal."""
        validate_transition("pending_review", "approved")

    def test_pending_review_to_rejected(self) -> None:
        """pending_review → rejected is legal."""
        validate_transition("pending_review", "rejected")

    def test_pending_review_to_closed(self) -> None:
        """pending_review → closed is legal."""
        validate_transition("pending_review", "closed")

    def test_approved_to_action_pending(self) -> None:
        """approved → action_pending is legal."""
        validate_transition("approved", "action_pending")

    def test_approved_to_closed(self) -> None:
        """approved → closed is legal."""
        validate_transition("approved", "closed")

    def test_action_pending_to_action_completed(self) -> None:
        """action_pending → action_completed is legal."""
        validate_transition("action_pending", "action_completed")

    def test_action_pending_to_closed(self) -> None:
        """action_pending → closed is legal."""
        validate_transition("action_pending", "closed")

    def test_action_completed_to_verified(self) -> None:
        """action_completed → verified is legal."""
        validate_transition("action_completed", "verified")

    def test_action_completed_to_recovered(self) -> None:
        """action_completed → recovered is legal."""
        validate_transition("action_completed", "recovered")

    def test_action_completed_to_closed(self) -> None:
        """action_completed → closed is legal."""
        validate_transition("action_completed", "closed")

    def test_verified_to_closed(self) -> None:
        """verified → closed is legal."""
        validate_transition("verified", "closed")

    def test_recovered_to_closed(self) -> None:
        """recovered → closed is legal."""
        validate_transition("recovered", "closed")

    def test_rejected_to_closed(self) -> None:
        """rejected → closed is legal."""
        validate_transition("rejected", "closed")

    def test_false_positive_to_closed(self) -> None:
        """false_positive → closed is legal."""
        validate_transition("false_positive", "closed")

    def test_legitimate_exception_to_closed(self) -> None:
        """legitimate_exception → closed is legal."""
        validate_transition("legitimate_exception", "closed")


class TestIllegalTransitions:
    """Test all illegal transitions are rejected."""

    def test_detected_to_approved(self) -> None:
        """detected → approved is ILLEGAL."""
        with pytest.raises(InvalidTransitionError, match=r"detected.*approved"):
            validate_transition("detected", "approved")

    def test_detected_to_recovered(self) -> None:
        """detected → recovered is ILLEGAL."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("detected", "recovered")

    def test_investigating_to_approved(self) -> None:
        """investigating → approved is ILLEGAL (skips pending_review)."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("investigating", "approved")

    def test_pending_review_to_investigating_legal(self) -> None:
        """pending_review → investigating is LEGAL (request more evidence)."""
        validate_transition("pending_review", "investigating")

    def test_pending_review_to_action_pending(self) -> None:
        """pending_review → action_pending is ILLEGAL (skips approved)."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("pending_review", "action_pending")

    def test_approved_to_action_completed(self) -> None:
        """approved → action_completed is ILLEGAL (skips action_pending)."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("approved", "action_completed")

    def test_action_pending_to_verified(self) -> None:
        """action_pending → verified is ILLEGAL (skips action_completed)."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("action_pending", "verified")

    def test_closed_to_anything(self) -> None:
        """closed → anything is ILLEGAL (terminal state)."""
        for target in ["detected", "investigating", "pending_review", "approved"]:
            with pytest.raises(InvalidTransitionError):
                validate_transition("closed", target)

    def test_false_positive_to_investigating(self) -> None:
        """false_positive → investigating is ILLEGAL."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("false_positive", "investigating")

    def test_recovered_to_investigating(self) -> None:
        """recovered → investigating is ILLEGAL."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("recovered", "investigating")

    def test_rejected_to_approved(self) -> None:
        """rejected → approved is ILLEGAL."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("rejected", "approved")

    def test_self_transition_detected(self) -> None:
        """detected → detected is ILLEGAL (no self-transitions)."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("detected", "detected")


class TestTerminalStates:
    """Tests for terminal state behavior."""

    def test_closed_is_terminal(self) -> None:
        """closed is a terminal state."""
        assert is_terminal("closed")

    def test_false_positive_is_terminal(self) -> None:
        """false_positive is a terminal state."""
        assert is_terminal("false_positive")

    def test_legitimate_exception_is_terminal(self) -> None:
        """legitimate_exception is a terminal state."""
        assert is_terminal("legitimate_exception")

    def test_detected_is_not_terminal(self) -> None:
        """detected is not a terminal state."""
        assert not is_terminal("detected")

    def test_pending_review_is_not_terminal(self) -> None:
        """pending_review is not a terminal state."""
        assert not is_terminal("pending_review")

    def test_all_terminal_statuses(self) -> None:
        """Terminal statuses match expected set."""
        assert {"closed", "false_positive", "legitimate_exception"} == TERMINAL_STATUSES


class TestGetAllowedTransitions:
    """Tests for get_allowed_transitions."""

    def test_detected_allows_two(self) -> None:
        """detected allows 2 transitions."""
        allowed = get_allowed_transitions("detected")
        assert allowed == {"investigating", "closed"}

    def test_pending_review_allows_four(self) -> None:
        """pending_review allows 4 transitions (including investigating for evidence re-run)."""
        allowed = get_allowed_transitions("pending_review")
        assert allowed == {"approved", "rejected", "investigating", "closed"}

    def test_closed_allows_none(self) -> None:
        """closed allows 0 transitions."""
        allowed = get_allowed_transitions("closed")
        assert allowed == set()

    def test_unknown_status_raises(self) -> None:
        """Unknown status raises ValueError."""
        with pytest.raises(ValueError, match="Unknown status"):
            get_allowed_transitions("bogus")


class TestCanTransitionTo:
    """Tests for can_transition_to (non-raising check)."""

    def test_legal_transition_returns_true(self) -> None:
        """Legal transition returns True."""
        assert can_transition_to("detected", "investigating") is True

    def test_illegal_transition_returns_false(self) -> None:
        """Illegal transition returns False."""
        assert can_transition_to("detected", "approved") is False

    def test_unknown_status_returns_false(self) -> None:
        """Unknown status returns False."""
        assert can_transition_to("bogus", "detected") is False


class TestInvalidTransitionError:
    """Tests for the error message quality."""

    def test_error_includes_statuses(self) -> None:
        """Error message includes both current and target status."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition("detected", "approved")
        assert "detected" in str(exc_info.value)
        assert "approved" in str(exc_info.value)

    def test_error_includes_allowed(self) -> None:
        """Error message includes allowed transitions."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition("detected", "approved")
        assert "investigating" in str(exc_info.value)
        assert "closed" in str(exc_info.value)

    def test_error_for_terminal_state(self) -> None:
        """Error message indicates terminal state."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition("closed", "detected")
        assert "terminal" in str(exc_info.value).lower()


class TestTransitionTableCompleteness:
    """Verify the transition table covers all statuses."""

    def test_all_statuses_in_table(self) -> None:
        """Every status has an entry in the transition table."""
        for status in ALL_STATUSES:
            assert status in TRANSITION_TABLE, f"Missing transition entry for {status}"

    def test_all_targets_are_valid_statuses(self) -> None:
        """All transition targets are valid statuses."""
        for source, targets in TRANSITION_TABLE.items():
            for target in targets:
                assert target in ALL_STATUSES, (
                    f"Invalid target '{target}' in transition from '{source}'"
                )
