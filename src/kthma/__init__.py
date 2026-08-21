from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class RecoveryCaseFeatures:
    recovery_case_id: str


@dataclass(frozen=True)
class GroundTruth:
    recovery_case_id: str
    recoverable: bool
    best_action: str
    expected_outcome: int
    amount: int


@dataclass(frozen=True)
class Split:
    features: tuple[RecoveryCaseFeatures, ...] = ()
    ground_truth: tuple[GroundTruth, ...] = ()


@dataclass(frozen=True)
class SplitDataset:
    development: Split = Split()
    holdout: Split = Split()


def generate(seed: int, n: int, config=None) -> SplitDataset:
    rng = Random(seed)
    ids = [f"rc_{i:04d}" for i in range(n)]
    rng.shuffle(ids)
    n_holdout = n // 5
    holdout_ids = ids[:n_holdout]
    development_ids = ids[n_holdout:]

    def features_for(case_ids: list[str]) -> tuple[RecoveryCaseFeatures, ...]:
        return tuple(RecoveryCaseFeatures(recovery_case_id=case_id) for case_id in case_ids)

    def truth_for(case_ids: list[str]) -> tuple[GroundTruth, ...]:
        return tuple(
            GroundTruth(
                recovery_case_id=case_id,
                recoverable=True,
                best_action="retry_payment",
                expected_outcome=0,
                amount=0,
            )
            for case_id in case_ids
        )

    return SplitDataset(
        development=Split(
            features=features_for(development_ids),
            ground_truth=truth_for(development_ids),
        ),
        holdout=Split(
            features=features_for(holdout_ids),
            ground_truth=truth_for(holdout_ids),
        ),
    )
