"""Learned recovery policy.

A recovery move is chosen by expected recovery value, learned from development
outcomes. The model sees model-visible features ONLY (never ground-truth
labels). A random forest naturally captures the non-linear interactions (e.g.
bank_timeout + card -> retry wins) that a linear rule table can't, and
'do_nothing' is learned as a first-class action (intelligent refusal).
"""

from __future__ import annotations

import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from kthma.models import RecoveryCaseFeatures, Split

_TYPE_ORDER = ("payment_failure", "checkout_abandonment", "subscription_failure", "repeated_failure")
_METHOD_ORDER = ("upi", "card", "netbanking", "wallet")
_REASON_ORDER = ("bank_timeout", "insufficient_funds", "authentication_failed", "mandate_debit_declined", "none")

INTERVENTION_ACTIONS = ("retry_payment", "payment_link", "retry_subscription", "reminder", "alternate_method")


def context_vector(features: RecoveryCaseFeatures) -> list[float]:
    """Deterministic, order-stable numeric vector over model-visible features."""
    reason = features.failure_reason or "none"
    vec: list[float] = [1.0 if features.leakage_type == t else 0.0 for t in _TYPE_ORDER]
    vec += [1.0 if features.payment_method == m else 0.0 for m in _METHOD_ORDER]
    vec += [1.0 if reason == r else 0.0 for r in _REASON_ORDER]
    vec += [
        float(features.amount) / 20000.0,
        float(features.attempt_count),
        float(features.prior_failures),
        float(features.prior_successful_payments),
        float(features.days_since_last_success) / 60.0,
        1.0 if features.subscription_flag else 0.0,
        1.0 if features.checkout_entered_flag else 0.0,
    ]
    return vec


def _matrix(features) -> np.ndarray:
    return np.array([context_vector(f) for f in features], dtype=float)


class RecoveryPolicy:
    def __init__(self, model: RandomForestClassifier) -> None:
        self.model = model

    def predict(self, features: RecoveryCaseFeatures) -> tuple[str, float]:
        """Return (best_action, probability_of_success)."""
        vector = np.array(context_vector(features), dtype=float).reshape(1, -1)
        action = str(self.model.predict(vector)[0])  # type: ignore[index]
        proba = self.model.predict_proba(vector)[0]
        cls = list(self.model.classes_)
        probability = float(proba[cls.index(action)])
        return action, probability


def fit_policy(development: Split, seed: int = 42) -> RecoveryPolicy:
    """Train on development ground truth (labels never reach prediction)."""
    X = _matrix(development.features)
    y = [g.best_action for g in development.ground_truth]
    n_estimators = int(os.environ.get("KTHMA_N_ESTIMATORS", "200"))
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        random_state=seed,
        n_jobs=1,
    )
    model.fit(X, y)
    return RecoveryPolicy(model)


def recovery_value(action: str, amount: int, probability: float) -> int:
    """amount x probability, zero for non-interventions."""
    if action not in INTERVENTION_ACTIONS:
        return 0
    return round(amount * probability)