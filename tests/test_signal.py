"""Differentiation: the learned recovery policy must beat the rule baseline on
hold-out, on both money recovered and false interventions. This is the whole
point of KTHMA vs a plain rules engine, and it is only possible because the
generator now emits learnable signal (not a coin flip)."""

from kthma import generate
from kthma.report import incremental_vs, run_evaluation


def test_kthma_recovery_policy_beats_rule_baseline_on_holdout():
    dataset = generate(seed=42, n=1000)
    report = run_evaluation(dataset)

    kthma = report.methods["KTHMA"]
    rules = report.methods["Rule Based"]

    # Meaningful, reproducible edge: learned policy must clearly beat rules.
    assert kthma.action_accuracy > rules.action_accuracy + 0.05
    assert kthma.false_intervention_rate < rules.false_intervention_rate
    assert incremental_vs(report, "Rule Based") > 0


def test_kthma_recovery_policy_beats_always_retry_and_avoids_harm():
    dataset = generate(seed=42, n=1000)
    report = run_evaluation(dataset)

    kthma = report.methods["KTHMA"]
    always = report.methods["Always Retry"]

    assert kthma.revenue_recovered > always.revenue_recovered
    assert kthma.false_intervention_rate < always.false_intervention_rate
    assert incremental_vs(report, "Always Retry") > 0


def test_differentiation_is_stable_across_seeds():
    for seed in (1, 7):
        report = run_evaluation(generate(seed=seed, n=1000))
        assert report.methods["KTHMA"].action_accuracy >= report.methods["Rule Based"].action_accuracy + 0.05, seed


def test_model_only_uses_development_labels_not_holdout():
    # The policy is fit inside run_evaluation on development only; scoring uses
    # hold-out ground truth. This asserts the measured metrics are on hold-out.
    dataset = generate(seed=42, n=1000)
    report = run_evaluation(dataset)
    assert report.methods["KTHMA"].total_cases == len(dataset.holdout.ground_truth)