"""CLI: --rows and --seed generate, persist, and print stats."""

from kthma.cli import build_stats, main


def test_build_stats_counts_and_overlap():
    stats = build_stats(seed=42, n=100)
    assert stats["development_rows"] == 80
    assert stats["holdout_rows"] == 20
    assert stats["id_overlap"] == 0
    assert stats["missing_leakage_types"] == []
    assert set(stats["leakage_type_counts"]) == {
        "payment_failure",
        "checkout_abandonment",
        "subscription_failure",
        "repeated_failure",
    }
    assert sum(stats["leakage_type_counts"].values()) == 100


def test_build_stats_flags_missing_types_below_minimum():
    stats = build_stats(seed=42, n=3)
    assert stats["missing_leakage_types"]  # below minimum n=20, types can be missing


def test_cli_writes_db_and_prints_stats(tmp_path, capsys):
    db_path = str(tmp_path / "dataset.sqlite3")
    exit_code = main(["--rows", "100", "--seed", "42", "--db", db_path])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "development_rows: 80" in out
    assert "holdout_rows: 20" in out
    assert "id_overlap: 0" in out
    assert "missing_leakage_types: none" in out

    import os

    assert os.path.exists(db_path)


def test_cli_is_reproducible(tmp_path, capsys):
    db1 = str(tmp_path / "a.sqlite3")
    db2 = str(tmp_path / "b.sqlite3")
    main(["--rows", "100", "--seed", "42", "--db", db1])
    stats1 = [ln for ln in capsys.readouterr().out.splitlines() if not ln.startswith("db:")]
    main(["--rows", "100", "--seed", "42", "--db", db2])
    stats2 = [ln for ln in capsys.readouterr().out.splitlines() if not ln.startswith("db:")]
    assert stats1 == stats2
