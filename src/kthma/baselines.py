"""Baseline recovery predictors. All see features only — never ground truth."""

from __future__ import annotations

from kthma.evaluation import Prediction
from kthma.models import RecoveryCaseFeatures, Split

RULE_ACTIONS = {
    "payment_failure": "retry_payment",
    "checkout_abandonment": "payment_link",
    "subscription_failure": "retry_subscription",
    "repeated_failure": "do_nothing",
}


class AlwaysRetryBaseline:
    name = "always_retry"

    def fit(self, split: Split) -> None:  # no learning
        return None

    def predict(self, features: RecoveryCaseFeatures) -> Prediction:
        return Prediction(
            recovery_case_id=features.recovery_case_id,
            recoverable=True,
            action="retry_payment",
        )


class RuleBasedBaseline:
    name = "rule_based"

    def fit(self, split: Split) -> None:  # no learning
        return None

    def predict(self, features: RecoveryCaseFeatures) -> Prediction:
        action = RULE_ACTIONS.get(features.leakage_type, "retry_payment")
        recoverable = features.leakage_type != "repeated_failure"
        return Prediction(
            recovery_case_id=features.recovery_case_id,
            recoverable=recoverable,
            action=action if recoverable else "do_nothing",
        )


class MLOnlyBaseline:
    """Pure-python logistic regression predicting recoverable; action from rules."""

    name = "ml_only"

    def __init__(self, learning_rate: float = 0.1, epochs: int = 300) -> None:
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.weights: list[float] = []
        self.bias = 0.0

    @staticmethod
    def _vector(f: RecoveryCaseFeatures) -> list[float]:
        return [
            1.0 if f.leakage_type == "repeated_failure" else 0.0,
            float(f.attempt_count),
            float(f.prior_failures),
            float(f.prior_successful_payments),
            float(f.days_since_last_success) / 60.0,
            1.0 if f.subscription_flag else 0.0,
        ]

    def fit(self, split: Split) -> None:
        vectors = [self._vector(f) for f in split.features]
        labels = [1.0 if g.recoverable else 0.0 for g in split.ground_truth]
        n_features = len(vectors[0])
        self.weights = [0.0] * n_features
        self.bias = 0.0
        for _ in range(self.epochs):
            for vec, label in zip(vectors, labels):
                z = self.bias + sum(w * x for w, x in zip(self.weights, vec))
                p = 1.0 / (1.0 + pow(2.718281828459045, -z))
                error = p - label
                self.bias -= self.learning_rate * error
                for i, x in enumerate(vec):
                    self.weights[i] -= self.learning_rate * error * x

    def predict(self, features: RecoveryCaseFeatures) -> Prediction:
        z = self.bias + sum(w * x for w, x in zip(self.weights, self._vector(features)))
        p_recoverable = 1.0 / (1.0 + pow(2.718281828459045, -z))
        recoverable = p_recoverable >= 0.5
        action = RULE_ACTIONS.get(features.leakage_type, "retry_payment")
        return Prediction(
            recovery_case_id=features.recovery_case_id,
            recoverable=recoverable,
            action=action if recoverable else "do_nothing",
        )
