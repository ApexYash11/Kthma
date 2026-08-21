"""generate(seed, n, config) returns an 80/20 split."""

from kthma import generate


def test_generate_splits_one_hundred_rows_eighty_twenty():
    dataset = generate(seed=42, n=100)

    assert len(dataset.development.features) == 80
    assert len(dataset.holdout.features) == 20
    assert len(dataset.development.ground_truth) == 80
    assert len(dataset.holdout.ground_truth) == 20


def test_development_and_holdout_recovery_case_ids_do_not_overlap():
    dataset = generate(seed=42, n=100)
    development_ids = {row.recovery_case_id for row in dataset.development.features}
    holdout_ids = {row.recovery_case_id for row in dataset.holdout.features}

    assert development_ids.isdisjoint(holdout_ids)
    assert len(development_ids) == 80
    assert len(holdout_ids) == 20


def test_same_seed_reproduces_recovery_case_ids():
    first = generate(seed=42, n=100)
    second = generate(seed=42, n=100)

    assert [row.recovery_case_id for row in first.development.features] == [
        row.recovery_case_id for row in second.development.features
    ]
    assert [row.recovery_case_id for row in first.holdout.features] == [
        row.recovery_case_id for row in second.holdout.features
    ]


def test_ground_truth_has_hidden_labels_and_amount():
    dataset = generate(seed=42, n=20)
    row = dataset.development.ground_truth[0]

    assert row.recovery_case_id
    assert isinstance(row.recoverable, bool)
    assert row.best_action
    assert isinstance(row.expected_outcome, int)
    assert isinstance(row.amount, int)


FORBIDDEN_FEATURE_FIELDS = frozenset(
    {"recoverable", "best_action", "expected_outcome", "intended_scenario"}
)


def test_features_do_not_expose_ground_truth_fields():
    dataset = generate(seed=42, n=20)
    for row in (*dataset.development.features, *dataset.holdout.features):
        assert FORBIDDEN_FEATURE_FIELDS.isdisjoint(row.__dataclass_fields__)


def test_n_of_twenty_includes_all_four_leakage_types():
    dataset = generate(seed=42, n=20)
    types = {row.leakage_type for row in (*dataset.development.features, *dataset.holdout.features)}
    assert types == {
        "payment_failure",
        "checkout_abandonment",
        "subscription_failure",
        "repeated_failure",
    }
