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


def test_generate_config_is_available_on_the_seam():
    from kthma import GenerateConfig

    config = GenerateConfig()
    dataset = generate(seed=42, n=20, config=config)

    assert len(dataset.development.features) + len(dataset.holdout.features) == 20


def test_same_seed_reproduces_full_dataset():
    first = generate(seed=42, n=50)
    second = generate(seed=42, n=50)

    assert first.development.features == second.development.features
    assert first.development.ground_truth == second.development.ground_truth
    assert first.holdout.features == second.holdout.features
    assert first.holdout.ground_truth == second.holdout.ground_truth


def test_amounts_are_positive_and_vary():
    dataset = generate(seed=42, n=100)
    amounts = [row.amount for row in (*dataset.development.ground_truth, *dataset.holdout.ground_truth)]

    assert all(isinstance(a, int) and a > 0 for a in amounts)
    assert len(set(amounts)) > 1


def test_best_action_varies_by_scenario():
    dataset = generate(seed=42, n=100)
    actions = {row.best_action for row in (*dataset.development.ground_truth, *dataset.holdout.ground_truth)}

    assert {"retry_payment", "payment_link", "do_nothing"}.issubset(actions)


def test_repeated_failure_cases_are_not_recoverable():
    dataset = generate(seed=42, n=200)
    pairs = {}
    for split in (dataset.development, dataset.holdout):
        features = {f.recovery_case_id: f for f in split.features}
        for gt in split.ground_truth:
            pairs[features[gt.recovery_case_id].leakage_type] = gt

    do_nothing = pairs["repeated_failure"]
    assert do_nothing.recoverable is False
    assert do_nothing.best_action == "do_nothing"
    assert do_nothing.expected_outcome == 0


def test_recoverable_ground_truth_matches_features_by_case_id():
    dataset = generate(seed=42, n=100)
    feature_ids = {f.recovery_case_id for f in dataset.development.features}
    truth_ids = {g.recovery_case_id for g in dataset.development.ground_truth}

    assert feature_ids == truth_ids


def test_n_of_twenty_includes_all_four_leakage_types():
    dataset = generate(seed=42, n=20)
    types = {row.leakage_type for row in (*dataset.development.features, *dataset.holdout.features)}
    assert types == {
        "payment_failure",
        "checkout_abandonment",
        "subscription_failure",
        "repeated_failure",
    }
