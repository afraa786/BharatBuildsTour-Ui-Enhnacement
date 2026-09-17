import pytest

from app.modules.runs.state_machine import InvalidTransition, RunStatus, assert_valid_transition


def test_happy_path_transitions_are_allowed() -> None:
    path = [
        RunStatus.RECEIVED,
        RunStatus.NORMALIZING,
        RunStatus.CHECKING_STOCK,
        RunStatus.CHECKING_PRICE,
        RunStatus.QUOTE_CREATED,
        RunStatus.QUOTE_SENT,
        RunStatus.ACCEPTED,
        RunStatus.PAYMENT_LINK_SENT,
        RunStatus.PAYMENT_PENDING,
        RunStatus.PAYMENT_CONFIRMED,
        RunStatus.INVOICE_GENERATED,
        RunStatus.ORDER_CONFIRMED,
    ]
    for current, target in zip(path, path[1:], strict=False):
        assert_valid_transition(current, target)


def test_cannot_skip_states() -> None:
    with pytest.raises(InvalidTransition):
        assert_valid_transition(RunStatus.RECEIVED, RunStatus.QUOTE_SENT)


def test_terminal_states_have_no_outgoing_transitions() -> None:
    with pytest.raises(InvalidTransition):
        assert_valid_transition(RunStatus.ORDER_CONFIRMED, RunStatus.RECEIVED)
    with pytest.raises(InvalidTransition):
        assert_valid_transition(RunStatus.REJECTED, RunStatus.QUOTE_CREATED)
