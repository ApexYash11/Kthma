"""Tiered policy gate: LOW auto-execute, MEDIUM approval, HIGH explicit
approval, and a HARD cap above which money-moving actions are blocked.
AGENTS.md:  LOW RISK -> auto, MEDIUM RISK -> approval,
            HIGH RISK / MONEY-MOVING -> explicit approval.
"""

from kthma.pipeline import Decision, PolicyVerdict, apply_policy
from kthma.execution import SimulatorExecutor, ExecutionRequest
from kthma.models import RecoveryCaseFeatures

CF = RecoveryCaseFeatures(
    recovery_case_id="rc_00001",
    leakage_type="payment_failure",
    amount=1299,
    currency="INR",
    payment_method="card",
    failure_reason="bank_timeout",
    attempt_count=1,
    last_attempt_at="2026-06-01T09:00:00",
    customer_id="cust_0001",
    prior_successful_payments=5,
    prior_failures=0,
    days_since_last_success=2,
    subscription_flag=False,
    checkout_entered_flag=False,
)


def _decision(action: str, amount: int = 1299) -> Decision:
    return Decision(
        recovery_case_id=CF.recovery_case_id,
        action=action,
        amount=amount,
        probability_of_success=0.7,
        expected_recovery_value=round(amount * 0.7),
        rationale="test",
    )


def test_do_nothing_is_low_risk_and_auto() -> None:
    v: PolicyVerdict = apply_policy(_decision("do_nothing"))
    assert v.risk_level == "low"
    assert v.requires_approval is False


def test_reminder_is_low_risk_and_auto() -> None:
    # audit-only reminder, no money moves -> auto-execute
    v: PolicyVerdict = apply_policy(_decision("reminder"))
    assert v.risk_level == "low"
    assert v.requires_approval is False


def test_medium_risk_intervention_requires_approval() -> None:
    v: PolicyVerdict = apply_policy(_decision("payment_link", amount=4999))
    assert v.risk_level == "medium"
    assert v.requires_approval is True


def test_high_risk_large_retry_requires_explicit_approval() -> None:
    v: PolicyVerdict = apply_policy(_decision("retry_payment", amount=60000))
    assert v.risk_level == "high"
    assert v.requires_approval is True


def test_blocked_above_hard_cap_is_never_executed() -> None:
    v: PolicyVerdict = apply_policy(_decision("retry_subscription", amount=999999))
    assert v.risk_level == "blocked"
    assert v.requires_approval is False  # approval is moot: we refuse to act


def test_blocked_action_renders_no_execution_in_run_case() -> None:
    from kthma.pipeline import run_case

    f = RecoveryCaseFeatures(
        recovery_case_id="rc_block",
        leakage_type="payment_failure",
        amount=999999,
        currency="INR",
        payment_method="card",
        failure_reason="bank_timeout",
        attempt_count=1,
        last_attempt_at="2026-06-01T09:00:00",
        customer_id="cust_1",
        prior_successful_payments=10,
        prior_failures=0,
        days_since_last_success=1,
        subscription_flag=False,
        checkout_entered_flag=False,
    )
    report = run_case(f, SimulatorExecutor())
    assert report.policy.risk_level == "blocked"
    assert report.verification.outcome == "no_action_taken"
    assert report.decision.action != "do_nothing"
    # blocked money-moving action must not be passed to an executor
    executor = SimulatorExecutor()
    executed = executor.execute(
        ExecutionRequest(f.recovery_case_id, report.decision.action, f.amount, approved=False)
    )
    assert "blocked" in executed.detail