from dataclasses import dataclass, field


@dataclass(frozen=True)
class GenerateConfig:
    leakage_type_weights: dict[str, float] = field(
        default_factory=lambda: {
            "payment_failure": 0.40,
            "checkout_abandonment": 0.30,
            "subscription_failure": 0.20,
            "repeated_failure": 0.10,
        }
    )
    recoverable_probability_by_type: dict[str, float] = field(
        default_factory=lambda: {
            "payment_failure": 0.85,
            "checkout_abandonment": 0.80,
            "subscription_failure": 0.90,
            "repeated_failure": 0.0,
        }
    )


@dataclass(frozen=True)
class RecoveryCaseFeatures:
    recovery_case_id: str
    leakage_type: str
    currency: str
    payment_method: str
    failure_reason: str | None
    attempt_count: int
    last_attempt_at: str
    customer_id: str
    prior_successful_payments: int
    prior_failures: int
    days_since_last_success: int
    subscription_flag: bool
    checkout_entered_flag: bool


@dataclass(frozen=True)
class GroundTruth:
    recovery_case_id: str
    recoverable: bool
    best_action: str
    expected_outcome: int
    amount: int
    intended_scenario: str


@dataclass(frozen=True)
class Split:
    features: tuple[RecoveryCaseFeatures, ...] = ()
    ground_truth: tuple[GroundTruth, ...] = ()


@dataclass(frozen=True)
class SplitDataset:
    development: Split = Split()
    holdout: Split = Split()
