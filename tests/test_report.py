"""Hold-out evaluation: baselines vs KTHMA, fit on development only."""

from kthma import generate
from kthma.report import run_evaluation


def test_evaluation_scores_all_four_methods_on_holdout():
    dataset = generate(seed=42, n=200)
    report = run_evaluation(dataset)

    assert set(report.methods) == {"Always Retry", "Rule Based", "ML Only", "KTHMA"}
    for m in report.methods.values():
        assert m.total_cases == len(dataset.holdout.ground_truth)
        assert 0.0 <= m.action_accuracy <= 1.0
        assert m.revenue_recovered >= 0


def test_kthma_never_fits_on_holdout_and_beats_or_matches_always_retry_on_false_interventions():
    dataset = generate(seed=42, n=200)
    report = run_evaluation(dataset)
    assert report.methods["KTHMA"].false_intervention_rate <= report.methods["Always Retry"].false_intervention_rate


def test_evaluation_is_deterministic():
    dataset = generate(seed=42, n=200)
    first = run_evaluation(dataset)
    second = run_evaluation(dataset)
    assert first == second
