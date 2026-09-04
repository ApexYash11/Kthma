"""Agent pipeline: DETECT -> DIAGNOSE -> DECIDE -> POLICY -> ACT -> VERIFY."""

from kthma import generate
from kthma.execution import SimulatorExecutor
from kthma.pipeline import run_case


def _case_with_type(leakage_type: str):
    dataset = generate(seed=7, n=100)
    for f in dataset.development.features:
        if f.leakage_type == leakage_type:
            return f
    raise AssertionError(f"no {leakage_type} case in fixture")


def test_report_contains_all_six_stages_in_order():
    # With approved=True, a medium-risk money action runs end-to-end.
    report = run_case(_case_with_type("payment_failure"), SimulatorExecutor(), approved=True)
    stages = [step.stage for step in report.timeline]
    assert stages == ["DETECT", "DIAGNOSE", "DECIDE", "POLICY", "ACT", "VERIFY"]


def test_detection_reports_revenue_at_risk():
    report = run_case(_case_with_type("payment_failure"), SimulatorExecutor())
    assert report.detection.revenue_at_risk > 0
    assert report.detection.leakage_type == "payment_failure"


def test_diagnosis_names_root_cause_without_labels():
    report = run_case(_case_with_type("payment_failure"), SimulatorExecutor())
    assert report.diagnosis.root_cause
    assert not hasattr(report.diagnosis, "recoverable")
    assert not hasattr(report.diagnosis, "best_action")


def test_decision_sets_expected_recovery_value():
    report = run_case(_case_with_type("payment_failure"), SimulatorExecutor())
    d = report.decision
    assert d.action in {"retry_payment", "payment_link", "reminder", "alternate_method", "retry_subscription", "escalate", "do_nothing"}
    assert 0.0 <= d.probability_of_success <= 1.0
    assert d.expected_recovery_value == round(d.amount * d.probability_of_success)
    assert d.rationale  # why is explainable


def test_policy_requires_approval_for_money_moving_and_allows_do_nothing():
    money_moving = run_case(_case_with_type("payment_failure"), SimulatorExecutor()).policy
    do_nothing = run_case(_case_with_type("repeated_failure"), SimulatorExecutor()).policy
    assert money_moving.requires_approval is True
    assert do_nothing.requires_approval is False
    assert do_nothing.action == "do_nothing"


def test_repeated_failure_is_not_executed():
    report = run_case(_case_with_type("repeated_failure"), SimulatorExecutor())
    assert report.decision.action == "do_nothing"
    assert report.verification.recovered_amount == 0
    assert report.verification.outcome == "no_action_taken"


def test_recoverable_case_is_executed_and_verified():
    # approved=True so the medium-risk action actually executes
    report = run_case(_case_with_type("checkout_abandonment"), SimulatorExecutor(), approved=True)
    assert report.execution is not None
    assert report.execution.adapter == "SIMULATOR"
    assert report.verification.outcome == "recovered"
    assert report.verification.recovered_amount == report.decision.amount


def test_run_case_is_deterministic():
    f = _case_with_type("payment_failure")
    first = run_case(f, SimulatorExecutor())
    second = run_case(f, SimulatorExecutor())
    assert first == second
