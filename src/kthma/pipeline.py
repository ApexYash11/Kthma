"""Pipeline stages with typed contracts. LLM only at judgment stages via a port."""

from __future__ import annotations

from dataclasses import dataclass, field

from kthma.execution import ExecutionRequest, ExecutionResult, Executor, SimulatorExecutor
from kthma.models import RecoveryCaseFeatures
from kthma.recovery_model import RecoveryPolicy, recovery_value

MONEY_MOVING = frozenset({"retry_payment", "retry_subscription", "payment_link"})
# AGENTS.md policy tiers, made concrete:
#   LOW    -> auto-execute (audit-only / refusal / no money moves)
#   MEDIUM -> require operator approval
#   HIGH   -> require explicit approval (large money-moving action)
#   blocked -> hard cap exceeded: never execute, even with approval
AUTO_ACTIONS = frozenset({"do_nothing", "escalate", "reminder", "alternate_method"})
MEDIUM_AMOUNT_CAP = 10_000   # at/below: money-moving is medium risk
HIGH_AMOUNT_CAP = 50_000     # above: money-moving is high risk (explicit approval)
BLOCK_AMOUNT_CAP = 100_000   # above: refuse to act at all


@dataclass(frozen=True)
class Detection:
    recovery_case_id: str
    leakage_type: str
    revenue_at_risk: int


@dataclass(frozen=True)
class Diagnosis:
    root_cause: str
    confidence: float
    evidence: list[str]


@dataclass(frozen=True)
class Decision:
    recovery_case_id: str
    action: str
    amount: int
    probability_of_success: float
    expected_recovery_value: int
    rationale: str


@dataclass(frozen=True)
class PolicyVerdict:
    action: str
    risk_level: str
    requires_approval: bool
    blocked: bool = False


@dataclass(frozen=True)
class Verification:
    outcome: str
    recovered_amount: int


@dataclass(frozen=True)
class TimelineStep:
    stage: str
    detail: str


@dataclass(frozen=True)
class CaseReport:
    detection: Detection
    diagnosis: Diagnosis
    decision: Decision
    policy: PolicyVerdict
    execution: ExecutionResult | None
    verification: Verification
    timeline: list[TimelineStep] = field(default_factory=list)


def detect(features: RecoveryCaseFeatures) -> Detection:
    return Detection(
        recovery_case_id=features.recovery_case_id,
        leakage_type=features.leakage_type,
        revenue_at_risk=features.amount,
    )


def diagnose(features: RecoveryCaseFeatures) -> Diagnosis:
    evidence = [
        f"leakage_type={features.leakage_type}",
        f"failure_reason={features.failure_reason or 'none'}",
        f"attempt_count={features.attempt_count}",
        f"prior_failures={features.prior_failures}",
        f"prior_successful_payments={features.prior_successful_payments}",
        f"days_since_last_success={features.days_since_last_success}",
    ]
    if features.leakage_type == "repeated_failure":
        cause, confidence = "repeated_failed_attempts_low_recovery_probability", 0.9
    elif features.leakage_type == "checkout_abandonment":
        cause, confidence = "customer_entered_payment_flow_then_abandoned", 0.85
    elif features.leakage_type == "subscription_failure":
        cause, confidence = "mandate_debit_declined_with_payment_history", 0.75
    elif features.failure_reason == "bank_timeout":
        cause, confidence = "bank_timeout_high_purchase_intent", 0.8
    elif features.failure_reason == "insufficient_funds":
        cause, confidence = "insufficient_funds_temporary", 0.6
    else:
        cause, confidence = "payment_failed", 0.5
    return Diagnosis(root_cause=cause, confidence=confidence, evidence=evidence)


def _probability(features: RecoveryCaseFeatures) -> float:
    base = {
        "payment_failure": 0.7,
        "checkout_abandonment": 0.65,
        "subscription_failure": 0.75,
        "repeated_failure": 0.1,
    }[features.leakage_type]
    base += min(features.prior_successful_payments, 10) * 0.02
    base -= features.prior_failures * 0.05
    return round(min(max(base, 0.05), 0.95), 2)


def decide(
    features: RecoveryCaseFeatures,
    policy: RecoveryPolicy | None = None,
) -> Decision:
    """Choose a recovery action. When a learned policy is provided it selects by
    expected recovery value (amount x probability, do_nothing on the same axis);
    otherwise a deterministic rule default covers cold-start and unit tests."""
    if policy is not None:
        action, probability = policy.predict(features)
        expected = recovery_value(action, features.amount, probability)
        if action == "do_nothing":
            rationale = "learned: value below intervention cost; do not recover"
        else:
            rationale = f"learned policy ranked {action} highest by expected recovery value"
        return Decision(
            recovery_case_id=features.recovery_case_id,
            action=action,
            amount=features.amount,
            probability_of_success=round(probability, 2),
            expected_recovery_value=expected,
            rationale=rationale,
        )

    if features.leakage_type == "repeated_failure":
        action = "do_nothing"
        rationale = "multiple recent failures with low recovery probability; do not retry"
    elif features.leakage_type == "subscription_failure":
        action = "retry_subscription"
        rationale = "recurring charge failed with payment history; retry subscription"
    elif features.leakage_type == "checkout_abandonment":
        action = "payment_link"
        rationale = "customer entered payment flow then left; link beats repeated retry"
    elif features.failure_reason == "bank_timeout" and features.prior_successful_payments >= 3:
        action = "retry_payment"
        rationale = "bank timeout with strong payment history; retry is safe"
    elif features.leakage_type == "payment_failure" and features.failure_reason == "bank_timeout":
        action = "retry_payment"
        rationale = "transient bank timeout; retry is safe"
    else:
        action = "retry_payment"
        rationale = f"recommended for {features.leakage_type} based on evidence"

    probability = _probability(features)
    return Decision(
        recovery_case_id=features.recovery_case_id,
        action=action,
        amount=features.amount,
        probability_of_success=probability,
        expected_recovery_value=round(features.amount * probability),
        rationale=rationale,
    )


def apply_policy(decision: Decision) -> PolicyVerdict:
    # Audit-only / refusal actions auto-execute (they move no money).
    if decision.action in AUTO_ACTIONS:
        return PolicyVerdict(decision.action, "low", False)
    # Unknown intervention that isn't a recognized money mover -> approval.
    if decision.action not in MONEY_MOVING:
        return PolicyVerdict(decision.action, "medium", True)
    # Money-moving: respect the amount caps (safety / Rs cap, AGENTS.md).
    if decision.amount > BLOCK_AMOUNT_CAP:
        return PolicyVerdict(decision.action, "blocked", False, blocked=True)
    if decision.amount > HIGH_AMOUNT_CAP:
        return PolicyVerdict(decision.action, "high", True)
    return PolicyVerdict(decision.action, "medium", True)


def plan_case(
    features: RecoveryCaseFeatures,
    policy: RecoveryPolicy | None = None,
) -> CaseReport:
    """Plan a recovery case without executing any money-moving action.

    Used by GET endpoints and the dashboard case list so that no action is
    ever performed until an operator explicitly approves it via POST /approve.
    The pipeline runs through POLICY; execution is left as None and the
    verification outcome is ``pending_approval`` when the action requires it.
    """
    timeline: list[TimelineStep] = []

    detection = detect(features)
    timeline.append(TimelineStep("DETECT", f"leakage detected: {detection.leakage_type}"))

    diagnosis = diagnose(features)
    timeline.append(TimelineStep("DIAGNOSE", f"root cause: {diagnosis.root_cause}"))

    decision = decide(features, policy)
    timeline.append(
        TimelineStep("DECIDE", f"action={decision.action} erv=Rs{decision.expected_recovery_value}")
    )

    verdict = apply_policy(decision)
    timeline.append(
        TimelineStep("POLICY", f"risk={verdict.risk_level} requires_approval={verdict.requires_approval}")
    )

    if decision.action == "do_nothing" or verdict.blocked:
        note = (
            "no action taken; case closed without intervention"
            if not verdict.blocked
            else f"action blocked by policy: {verdict.risk_level} risk exceeds safe limit"
        )
        verification = Verification("no_action_taken", 0)
        timeline.append(TimelineStep("VERIFY", note))
    elif verdict.requires_approval:
        verification = Verification("pending_approval", 0)
        timeline.append(TimelineStep("VERIFY", "awaiting operator approval before execution"))
    else:
        # Low-risk auto-execute action (reminder / escalate / alternate_method):
        # these move no money, so planning is also the final state.
        verification = Verification("auto_planned", 0)
        timeline.append(TimelineStep("VERIFY", "low-risk action; no execution on read path"))

    return CaseReport(
        detection=detection,
        diagnosis=diagnosis,
        decision=decision,
        policy=verdict,
        execution=None,
        verification=verification,
        timeline=timeline,
    )


def run_case(
    features: RecoveryCaseFeatures,
    executor: Executor | None = None,
    policy: RecoveryPolicy | None = None,
    approved: bool = False,
) -> CaseReport:
    """Run a recovery case end-to-end, optionally executing the action.

    Parameters
    ----------
    approved:
        Whether an operator has explicitly approved money-moving actions.
        Defaults to ``False`` so that forgetting to pass it never executes.
        Only ``POST /approve`` passes ``True``.
    """
    executor = executor or SimulatorExecutor()
    timeline: list[TimelineStep] = []

    detection = detect(features)
    timeline.append(TimelineStep("DETECT", f"leakage detected: {detection.leakage_type}"))

    diagnosis = diagnose(features)
    timeline.append(TimelineStep("DIAGNOSE", f"root cause: {diagnosis.root_cause}"))

    decision = decide(features, policy)
    timeline.append(
        TimelineStep("DECIDE", f"action={decision.action} erv=Rs{decision.expected_recovery_value}")
    )

    verdict = apply_policy(decision)
    timeline.append(
        TimelineStep("POLICY", f"risk={verdict.risk_level} requires_approval={verdict.requires_approval}")
    )

    execution: ExecutionResult | None = None
    if decision.action == "do_nothing" or verdict.blocked:
        note = (
            "no action taken; case closed without intervention"
            if not verdict.blocked
            else f"action blocked by policy: {verdict.risk_level} risk exceeds safe limit"
        )
        verification = Verification("no_action_taken", 0)
        timeline.append(TimelineStep("VERIFY", note))
    elif verdict.requires_approval and not approved:
        # Money-moving action that needs operator approval but was not approved.
        # Do not execute. This is the gate.
        verification = Verification("pending_approval", 0)
        timeline.append(TimelineStep("VERIFY", "awaiting operator approval before execution"))
    else:
        # Either the action is low-risk (auto) or the operator approved it.
        execution = executor.execute(
            ExecutionRequest(
                recovery_case_id=decision.recovery_case_id,
                action=decision.action,
                amount=decision.amount,
                approved=True,
            )
        )
        timeline.append(TimelineStep("ACT", f"adapter={execution.adapter} success={execution.success}"))
        if execution.success:
            verification = Verification("recovered", decision.amount)
            timeline.append(TimelineStep("VERIFY", f"recovered Rs{decision.amount}"))
        else:
            verification = Verification("failed", 0)
            timeline.append(TimelineStep("VERIFY", f"action failed: {execution.detail}"))

    return CaseReport(
        detection=detection,
        diagnosis=diagnosis,
        decision=decision,
        policy=verdict,
        execution=execution,
        verification=verification,
        timeline=timeline,
    )
