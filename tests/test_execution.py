"""Fail-closed Razorpay executor and labelled simulator (ADR 0003)."""

import pytest

from kthma.execution import ExecutionRequest, RazorpayExecutor, SimulatorExecutor


def test_grounded_simulator_only_recovers_world_recoverable_cases():
    from kthma.execution import GroundedSimulatorExecutor

    executor = GroundedSimulatorExecutor({"rc_1": True, "rc_2": False})
    good = executor.execute(ExecutionRequest("rc_1", "payment_link", 2499, approved=True))
    bad = executor.execute(ExecutionRequest("rc_2", "payment_link", 2499, approved=True))
    assert good.success is True
    assert bad.success is False
    assert bad.adapter == "SIMULATOR"


def test_simulator_is_labelled_and_never_fakes_razorpay():
    result = SimulatorExecutor().execute(
        ExecutionRequest("rc_1", "payment_link", 2499, approved=True)
    )
    assert result.adapter == "SIMULATOR"


def test_simulator_refuses_unapproved_money_moving_action():
    result = SimulatorExecutor().execute(
        ExecutionRequest("rc_1", "retry_payment", 2499, approved=False)
    )
    assert result.success is False


def test_razorpay_executor_fails_closed_without_keys(monkeypatch):
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    executor = RazorpayExecutor()
    assert executor.configured is False
    with pytest.raises(RuntimeError, match="fail closed"):
        executor.execute(ExecutionRequest("rc_1", "payment_link", 2499, approved=True))


def test_razorpay_executor_with_keys_still_refuses_unwired_calls(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_dummy")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "dummy")
    executor = RazorpayExecutor()
    assert executor.configured is True
    with pytest.raises(RuntimeError, match="not wired"):
        executor.execute(ExecutionRequest("rc_1", "payment_link", 2499, approved=True))
