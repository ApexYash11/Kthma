"""Decision fix tests: development split only (hold-out stays untouched)."""

from kthma import generate
from kthma.baselines import RuleBasedBaseline
from kthma.evaluation import Prediction, score
from kthma.pipeline import decide


def test_kthma_decides_subscription_cases_by_scenario_not_failure_reason():
    dataset = generate(seed=7, n=100)
    development = dataset.development
    subscription_cases = [
        f for f in development.features if f.leakage_type == "subscription_failure"
    ]
    assert subscription_cases  # fixture sanity
    for f in subscription_cases:
        assert decide(f).action == "retry_subscription", f


def test_kthma_matches_or_beats_rule_baseline_on_development():
    dataset = generate(seed=42, n=500)
    development = dataset.development
    rules = RuleBasedBaseline()
    rule_predictions = [rules.predict(f) for f in development.features]
    kthma_predictions = [
        Prediction(
            recovery_case_id=f.recovery_case_id,
            recoverable=decide(f).action != "do_nothing",
            action=decide(f).action,
        )
        for f in development.features
    ]
    rule_metrics = score(rule_predictions, development.ground_truth)
    kthma_metrics = score(kthma_predictions, development.ground_truth)
    assert kthma_metrics.action_accuracy >= rule_metrics.action_accuracy
    assert kthma_metrics.false_intervention_rate <= rule_metrics.false_intervention_rate
