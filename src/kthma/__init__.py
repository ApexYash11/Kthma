from datetime import datetime, timedelta
import math
from random import Random

from kthma.models import (
    GenerateConfig,
    GroundTruth,
    RecoveryCaseFeatures,
    Split,
    SplitDataset,
)
from kthma.recovery_model import RecoveryPolicy, fit_policy
from kthma.store import load_features, load_ground_truth, save_split

LEAKAGE_TYPES = (
    "payment_failure",
    "checkout_abandonment",
    "subscription_failure",
    "repeated_failure",
)

PAYMENT_METHODS = ("upi", "card", "netbanking", "wallet")

FAILURE_REASONS = {
    "payment_failure": ("bank_timeout", "insufficient_funds", "authentication_failed"),
    "subscription_failure": ("mandate_debit_declined", "bank_timeout"),
    "checkout_abandonment": (),
    "repeated_failure": ("insufficient_funds",),
}

AMOUNTS = (499, 999, 1299, 1999, 2499, 3499, 4999, 8999, 14999, 19999)

SCENARIO_ACTION = {
    "payment_failure": ("retry_payment", "payment_link"),
    "checkout_abandonment": ("payment_link",),
    "subscription_failure": ("retry_subscription",),
    "repeated_failure": ("do_nothing",),
}

SCENARIO_TAG = {
    "payment_failure": "A",
    "checkout_abandonment": "B",
    "subscription_failure": "C",
    "repeated_failure": "D",
}

RECOVERABLE_THRESHOLD = 0.5


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _sample_leakage_type(rng: Random, config: GenerateConfig) -> str:
    types = tuple(config.leakage_type_weights)
    weights = tuple(config.leakage_type_weights[t] for t in types)
    return rng.choices(types, weights=weights, k=1)[0]


def _resolve_outcome(features: RecoveryCaseFeatures, rng: Random) -> tuple[bool, str, int]:
    """Derive recoverable/best_action/expected_outcome from context.

    This is the learnable signal: recoverability and the best recovery move
    depend on a latent per-customer 'account health' plus feature interactions
    (e.g. bank_timeout + cards -> retry wins; auth/insufficient + wallet ->
    payment link wins; low health + repeated attempts -> nothing works). Small
    noise keeps it realistic. A rules engine (which keys off leakage_type only)
    is wrong on a meaningful share; a model that captures interactions learns it.
    """
    health = (
        0.5
        + min(features.prior_successful_payments, 10) * 0.06
        - features.prior_failures * 0.15
        + rng.gauss(0.0, 0.12)
    )

    if features.leakage_type == "repeated_failure":
        return False, "do_nothing", 0

    probs: dict[str, float] = {}
    if features.leakage_type == "payment_failure":
        retry_score = (
            (1.5 if features.failure_reason == "bank_timeout" else -0.4 if features.failure_reason == "insufficient_funds" else 0.0)
            + (0.4 if features.payment_method in ("upi", "card") else 0.0)
            + health
        )
        link_score = (
            (1.5 if features.failure_reason in ("authentication_failed", "insufficient_funds") else 0.0)
            + (0.3 if features.payment_method == "wallet" else 0.0)
            + health
            - 0.25 * (features.days_since_last_success / 30.0)
        )
        probs["retry_payment"] = _sigmoid(retry_score)
        probs["payment_link"] = _sigmoid(link_score)
    elif features.leakage_type == "checkout_abandonment":
        probs["payment_link"] = _sigmoid(health - 0.4 - 0.15 * (features.days_since_last_success / 30.0))
    elif features.leakage_type == "subscription_failure":
        probs["retry_subscription"] = _sigmoid(health + 0.3 - features.prior_failures * 0.2)

    best_action = max(probs, key=probs.get)
    recoverable = probs[best_action] >= RECOVERABLE_THRESHOLD
    if recoverable:
        return True, best_action, features.amount
    return False, "do_nothing", 0


def _build_row(index: int, leakage_type: str, rng: Random) -> tuple[RecoveryCaseFeatures, GroundTruth]:
    amount = rng.choice(AMOUNTS)
    payment_method = rng.choice(PAYMENT_METHODS)
    reasons = FAILURE_REASONS[leakage_type]
    failure_reason = rng.choice(reasons) if reasons else None
    attempt_count = {"repeated_failure": rng.randint(3, 7)}.get(leakage_type, rng.randint(1, 2))
    prior_failures = {"repeated_failure": rng.randint(2, 5)}.get(leakage_type, rng.randint(0, 1))
    prior_successes = {"subscription_failure": rng.randint(3, 12), "repeated_failure": rng.randint(0, 2)}.get(
        leakage_type, rng.randint(0, 10)
    )
    days_since_last_success = {"repeated_failure": rng.randint(10, 60)}.get(
        leakage_type, rng.randint(0, 30)
    )
    last_attempt_at = (
        datetime(2026, 6, 1, 9, 0, 0) + timedelta(minutes=rng.randint(0, 30 * 24 * 60))
    ).isoformat()

    features = RecoveryCaseFeatures(
        recovery_case_id=f"rc_{index:05d}",
        leakage_type=leakage_type,
        amount=amount,
        currency="INR",
        payment_method=payment_method,
        failure_reason=failure_reason,
        attempt_count=attempt_count,
        last_attempt_at=last_attempt_at,
        customer_id=f"cust_{rng.randint(0, 9999):04d}",
        prior_successful_payments=prior_successes,
        prior_failures=prior_failures,
        days_since_last_success=days_since_last_success,
        subscription_flag=leakage_type == "subscription_failure",
        checkout_entered_flag=leakage_type == "checkout_abandonment",
    )

    recoverable, best_action, expected_outcome = _resolve_outcome(features, rng)

    truth = GroundTruth(
        recovery_case_id=features.recovery_case_id,
        recoverable=recoverable,
        best_action=best_action,
        expected_outcome=expected_outcome,
        amount=amount,
        intended_scenario=SCENARIO_TAG[leakage_type],
    )
    return features, truth


def generate(seed: int, n: int, config: GenerateConfig | None = None) -> SplitDataset:
    config = config or GenerateConfig()
    rng = Random(seed)

    rows: list[tuple[RecoveryCaseFeatures, GroundTruth]] = []
    for index in range(n):
        leakage_type = _sample_leakage_type(rng, config)
        rows.append(_build_row(index, leakage_type, rng))

    if n >= len(LEAKAGE_TYPES):
        for slot, forced_type in enumerate(LEAKAGE_TYPES):
            rows[slot] = _build_row(slot, forced_type, rng)

    rng.shuffle(rows)

    n_holdout = n // 5
    holdout_rows = rows[:n_holdout]
    development_rows = rows[n_holdout:]

    def to_split(pairs: list[tuple[RecoveryCaseFeatures, GroundTruth]]) -> Split:
        return Split(
            features=tuple(f for f, _ in pairs),
            ground_truth=tuple(g for _, g in pairs),
        )

    return SplitDataset(
        development=to_split(development_rows),
        holdout=to_split(holdout_rows),
    )


__all__ = [
    "GenerateConfig",
    "GroundTruth",
    "RecoveryCaseFeatures",
    "Split",
    "SplitDataset",
    "generate",
    "load_features",
    "load_ground_truth",
    "save_split",
    "RecoveryPolicy",
    "fit_policy",
]
