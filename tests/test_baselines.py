"""Baselines: always-retry, rule-based, ML-only. Scored by the evaluation seam."""

from kthma import generate
from kthma.baselines import AlwaysRetryBaseline, MLOnlyBaseline, RuleBasedBaseline
from kthma.evaluation import score

FORBIDDEN = frozenset({"recoverable", "best_action", "expected_outcome", "intended_scenario"})


def _predictions(baseline, dataset):
    return [
        baseline.predict(f)
        for f in dataset.development.features
    ]


def test_every_baseline_outputs_action_and_recoverable_only():
    dataset = generate(seed=42, n=100)
    for baseline in (AlwaysRetryBaseline(), RuleBasedBaseline(), MLOnlyBaseline()):
        for p in _predictions(baseline, dataset):
            assert p.recovery_case_id
            assert isinstance(p.recoverable, bool)
            assert p.action in {
                "retry_payment",
                "payment_link",
                "reminder",
                "alternate_method",
                "retry_subscription",
                "escalate",
                "do_nothing",
            }


def test_baselines_never_see_ground_truth_fields():
    dataset = generate(seed=42, n=100)
    for baseline in (AlwaysRetryBaseline(), RuleBasedBaseline(), MLOnlyBaseline()):
        for f in dataset.development.features:
            assert FORBIDDEN.isdisjoint(f.__dataclass_fields__)
        baseline.fit(dataset.development)  # must not read labels into predictions structure


def test_always_retry_retries_everything():
    dataset = generate(seed=42, n=100)
    predictions = _predictions(AlwaysRetryBaseline(), dataset)
    assert all(p.action == "retry_payment" for p in predictions)
    assert all(p.recoverable for p in predictions)


def test_rule_based_does_not_retry_repeated_failures():
    dataset = generate(seed=42, n=100)
    predictions = {p.recovery_case_id: p for p in _predictions(RuleBasedBaseline(), dataset)}
    for f in dataset.development.features:
        if f.leakage_type == "repeated_failure":
            assert predictions[f.recovery_case_id].action == "do_nothing"
        if f.leakage_type == "checkout_abandonment":
            assert predictions[f.recovery_case_id].action == "payment_link"


def test_score_metrics_shape():
    dataset = generate(seed=42, n=100)
    metrics = score(_predictions(RuleBasedBaseline(), dataset), dataset.development.ground_truth)
    assert 0.0 <= metrics.action_accuracy <= 1.0
    assert 0.0 <= metrics.false_intervention_rate <= 1.0
    assert metrics.revenue_recovered >= 0
    assert metrics.recovered_cases >= 0


def test_perfect_predictions_score_full_recovery():
    dataset = generate(seed=42, n=100)
    truth_by_id = {g.recovery_case_id: g for g in dataset.development.ground_truth}
    from kthma.evaluation import Prediction

    predictions = [
        Prediction(
            recovery_case_id=g.recovery_case_id,
            recoverable=g.recoverable,
            action=g.best_action if g.recoverable else "do_nothing",
        )
        for g in dataset.development.ground_truth
    ]
    metrics = score(predictions, dataset.development.ground_truth)
    assert metrics.action_accuracy == 1.0
    assert metrics.false_intervention_rate == 0.0
    assert metrics.revenue_recovered == sum(
        g.amount for g in truth_by_id.values() if g.recoverable
    )
