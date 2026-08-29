"""Pipeline stages with typed contracts. LLM only at judgment stages via a port."""

from __future__ import annotations

from dataclasses import dataclass, field

from kthma.execution import ExecutionRequest, ExecutionResult, Executor, SimulatorExecutor
from kthma.models import RecoveryCaseFeatures

MONEY_MOVING = frozenset({"retry_payment", "retry_subscription", "payment_link"})


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
    elif features.failure_reason == "bank_timeout":
        cause, confidence = "bank_timeout_high_purchase_intent", 0.8
    elif features.failure_reason == "insufficient_funds":
        cause, confidence = "insufficient_funds_temporary", 0.6
    elif features.leakage_type == "subscription_failure":
        cause, confidence = "mandate_debit_declined_with_payment_history", 0.75
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


def decide(features: RecoveryCaseFeatures) -> Decision:
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
    if decision.action == "do_nothing":
        return PolicyVerdict(decision.action, "low", False)
    if decision.action in MONEY_MOVING:
        return PolicyVerdict(decision.action, "medium", True)
    return PolicyVerdict(decision.action, "medium", True)


def run_case(features: RecoveryCaseFeatures, executor: Executor | None = None) -> CaseReport:
    executor = executor or SimulatorExecutor()
    timeline: list[TimelineStep] = []

    detection = detect(features)
    timeline.append(TimelineStep("DETECT", f"leakage detected: {detection.leakage_type}"))

    diagnosis = diagnose(features)
    timeline.append(TimelineStep("DIAGNOSE", f"root cause: {diagnosis.root_cause}"))

    decision = decide(features)
    timeline.append(
        TimelineStep("DECIDE", f"action={decision.action} erv=Rs{decision.expected_recovery_value}")
    )

    policy = apply_policy(decision)
    timeline.append(
        TimelineStep("POLICY", f"risk={policy.risk_level} requires_approval={policy.requires_approval}")
    )

    execution: ExecutionResult | None = None
    if decision.action == "do_nothing":
        verification = Verification("no_action_taken", 0)
        timeline.append(TimelineStep("VERIFY", "no action taken; case closed without intervention"))
    else:
        execution = executor.execute(
            ExecutionRequest(
                recovery_case_id=decision.recovery_case_id,
                action=decision.action,
                amount=decision.amount,
                approved=policy.requires_approval,
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
        policy=policy,
        execution=execution,
        verification=verification,
        timeline=timeline,
    )
