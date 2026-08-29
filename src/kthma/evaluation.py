"""Evaluation seam: score predictions against ground truth."""

from __future__ import annotations

from dataclasses import dataclass

from kthma.models import GroundTruth

NON_INTERVENTIONS = frozenset({"do_nothing", "escalate"})


@dataclass(frozen=True)
class Prediction:
    recovery_case_id: str
    recoverable: bool
    action: str


@dataclass(frozen=True)
class Metrics:
    action_accuracy: float
    false_intervention_rate: float
    revenue_recovered: int
    recovered_cases: int
    total_cases: int


def score(predictions: list[Prediction], ground_truth: tuple[GroundTruth, ...]) -> Metrics:
    truth_by_id = {g.recovery_case_id: g for g in ground_truth}
    pred_by_id = {p.recovery_case_id: p for p in predictions}

    correct = 0
    false_interventions = 0
    non_recoverable = 0
    recovered = 0
    recovered_amount = 0

    for case_id, truth in truth_by_id.items():
        pred = pred_by_id.get(case_id)
        if pred is None:
            false_interventions += 0 if truth.recoverable else 1
            if not truth.recoverable:
                non_recoverable += 1
            continue

        if not truth.recoverable:
            non_recoverable += 1
            if pred.action not in NON_INTERVENTIONS:
                false_interventions += 1
            else:
                correct += 1
        elif pred.action == truth.best_action:
            correct += 1
            recovered += 1
            recovered_amount += truth.amount

    actionable = sum(
        1
        for truth in truth_by_id.values()
        if not truth.recoverable
    )
    total = len(truth_by_id)
    return Metrics(
        action_accuracy=correct / max(total, 1),
        false_intervention_rate=false_interventions / max(actionable or non_recoverable, 1),
        revenue_recovered=recovered_amount,
        recovered_cases=recovered,
        total_cases=total,
    )
