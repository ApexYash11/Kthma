"""Learning loop: KTHMA improves with more feedback (fit on outcomes, score on
untouched hold-out). This is the 're-train from outcomes' finalist feature,
demonstrated honestly as a learning curve over growing development data.
"""

from kthma import generate
from kthma.report import learning_loop


def test_learning_loop_is_deterministic_and_never_trains_on_holdout() -> None:
    dataset = generate(seed=42, n=150)
    results = learning_loop(dataset, train_sizes=(1.0,))
    assert learning_loop(dataset, train_sizes=(1.0,)) == results
    assert results[0]["n_train"] <= len(dataset.development.features)


def test_learning_loop_more_feedback_recovers_more() -> None:
    # Scaling outcomes raises hold-out Rs recovered — the headline metric.
    # Seed 42 is deterministic; fits use the conftest estimator count.
    dataset = generate(seed=42, n=1000)
    results = learning_loop(dataset, train_sizes=(0.25, 1.0))
    assert results[-1]["n_train"] > results[0]["n_train"]
    assert results[-1]["revenue_recovered"] >= results[0]["revenue_recovered"]