"""SQLite persist and reload: features vs ground truth stores."""

import os

import pytest

from kthma import generate


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "dataset.sqlite3")


@pytest.fixture()
def dataset():
    return generate(seed=42, n=100)


FORBIDDEN_FEATURE_FIELDS = frozenset(
    {"recoverable", "best_action", "expected_outcome", "intended_scenario"}
)


def test_round_trip_preserves_ids_amounts_leakage_types_and_labels(db_path, dataset):
    from kthma import load_features, load_ground_truth, save_split

    save_split(dataset, db_path)

    dev_features = load_features(db_path, "development")
    dev_truth = load_ground_truth(db_path, "development")
    hold_features = load_features(db_path, "holdout")

    original_dev_features = {f.recovery_case_id: f for f in dataset.development.features}
    loaded_dev_features = {f.recovery_case_id: f for f in dev_features}
    assert loaded_dev_features == original_dev_features
    assert {f.leakage_type for f in dev_features} == {
        f.leakage_type for f in dataset.development.features
    }
    original_dev_truth = {g.recovery_case_id: g for g in dataset.development.ground_truth}
    loaded_dev_truth = {g.recovery_case_id: g for g in dev_truth}
    assert loaded_dev_truth == original_dev_truth
    assert len(hold_features) == 20


def test_features_read_does_not_expose_ground_truth_fields(db_path, dataset):
    from kthma import load_features, save_split

    save_split(dataset, db_path)
    for split in ("development", "holdout"):
        for row in load_features(db_path, split):
            assert FORBIDDEN_FEATURE_FIELDS.isdisjoint(row.__dataclass_fields__)


def test_holdout_ground_truth_is_not_returned_by_features_only_read(db_path, dataset):
    from kthma import load_features, load_ground_truth, save_split

    save_split(dataset, db_path)

    holdout_feature_rows = load_features(db_path, "holdout")
    assert FORBIDDEN_FEATURE_FIELDS.isdisjoint(holdout_feature_rows[0].__dataclass_fields__)

    holdout_truth_ids = {g.recovery_case_id for g in load_ground_truth(db_path, "holdout")}
    assert holdout_truth_ids == {
        f.recovery_case_id for f in holdout_feature_rows
    }


def test_features_and_ground_truth_live_in_separate_stores(db_path, dataset):
    import sqlite3

    from kthma import save_split

    save_split(dataset, db_path)
    connection = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    connection.close()

    feature_tables = {t for t in tables if "feature" in t}
    truth_tables = {t for t in tables if "ground_truth" in t}
    assert feature_tables and truth_tables
    assert feature_tables.isdisjoint(truth_tables)
