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
    """Vectorized logistic regression (numpy) predicting recoverable; action from rules."""

    name = "ml_only"

    def __init__(self, learning_rate: float = 0.1, epochs: int = 300) -> None:
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.weights: np.ndarray | None = None
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
        import numpy as np

        X = np.array([self._vector(f) for f in split.features], dtype=float)
        y = np.array([1.0 if g.recoverable else 0.0 for g in split.ground_truth], dtype=float)
        self.weights = np.zeros(X.shape[1])
        self.bias = 0.0
        n = len(y)
        for _ in range(self.epochs):
            p = 1.0 / (1.0 + np.exp(-(self.bias + X @ self.weights)))
            err = p - y
            self.bias -= self.learning_rate * err.mean()
            self.weights -= self.learning_rate * ((X.T @ err) / n)

    def predict(self, features: RecoveryCaseFeatures) -> Prediction:
        import numpy as np

        vector = np.array(self._vector(features))
        weights = self.weights if self.weights is not None else np.zeros(vector.shape[0])
        z = self.bias + weights @ vector
        p_recoverable = 1.0 / (1.0 + float(np.exp(-z)))
        recoverable = p_recoverable >= 0.5
        action = RULE_ACTIONS.get(features.leakage_type, "retry_payment")
        return Prediction(
            recovery_case_id=features.recovery_case_id,
            recoverable=recoverable,
            action=action if recoverable else "do_nothing",
        )
