"""Command-line entry point: generate, persist, print stats."""

from __future__ import annotations

import argparse
from collections import Counter

from kthma import generate, load_features, load_ground_truth, save_split

MIN_N_ALL_TYPES = 20
ALL_LEAKAGE_TYPES = (
    "payment_failure",
    "checkout_abandonment",
    "subscription_failure",
    "repeated_failure",
)


def build_stats(seed: int, n: int) -> dict:
    dataset = generate(seed=seed, n=n)
    dev_ids = {f.recovery_case_id for f in dataset.development.features}
    hold_ids = {f.recovery_case_id for f in dataset.holdout.features}
    counts = Counter(f.leakage_type for f in (*dataset.development.features, *dataset.holdout.features))
    return {
        "development_rows": len(dev_ids),
        "holdout_rows": len(hold_ids),
        "id_overlap": len(dev_ids & hold_ids),
        "leakage_type_counts": {t: counts.get(t, 0) for t in ALL_LEAKAGE_TYPES},
        "missing_leakage_types": [t for t in ALL_LEAKAGE_TYPES if counts.get(t, 0) == 0],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kthma-generate", description="Generate KTHMA synthetic dataset")
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--db", default="dataset.sqlite3")
    args = parser.parse_args(argv)

    dataset = generate(seed=args.seed, n=args.rows)
    save_split(dataset, args.db)

    dev_ids = {f.recovery_case_id for f in dataset.development.features}
    hold_ids = {f.recovery_case_id for f in dataset.holdout.features}
    counts = Counter(f.leakage_type for f in (*dataset.development.features, *dataset.holdout.features))

    lines = [
        f"db: {args.db}",
        f"seed: {args.seed}",
        f"development_rows: {len(dev_ids)}",
        f"holdout_rows: {len(hold_ids)}",
        f"id_overlap: {len(dev_ids & hold_ids)}",
    ]
    for t in ALL_LEAKAGE_TYPES:
        lines.append(f"leakage_type_counts.{t}: {counts.get(t, 0)}")
    missing = [t for t in ALL_LEAKAGE_TYPES if counts.get(t, 0) == 0]
    if missing:
        lines.append(f"missing_leakage_types: {','.join(missing)} (minimum n for all types is {MIN_N_ALL_TYPES})")
    else:
        lines.append("missing_leakage_types: none")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())