"""Evaluation report: fit on development, score on hold-out (never tuned on it)."""

from __future__ import annotations

from dataclasses import dataclass

from kthma.baselines import AlwaysRetryBaseline, MLOnlyBaseline, RuleBasedBaseline
from kthma.evaluation import Metrics, Prediction, score
from kthma.models import SplitDataset
from kthma.pipeline import decide
from kthma.recovery_model import fit_policy


@dataclass(frozen=True)
class EvaluationReport:
    methods: dict[str, Metrics]
    split_used: str = "holdout"


def _kthma_predictions(dataset: SplitDataset, split: str) -> list[Prediction]:
    """KTHMA predicts with a policy learned on development only."""
    split_data = dataset.development if split == "development" else dataset.holdout
    policy = fit_policy(dataset.development, seed=42)
    predictions = []
    for f in split_data.features:
        decision = decide(f, policy)
        predictions.append(
            Prediction(
                recovery_case_id=f.recovery_case_id,
                recoverable=decision.action != "do_nothing",
                action=decision.action,
            )
        )
    return predictions


def run_evaluation(dataset: SplitDataset) -> EvaluationReport:
    development = dataset.development
    holdout = dataset.holdout

    always = AlwaysRetryBaseline()
    rules = RuleBasedBaseline()
    ml = MLOnlyBaseline()
    ml.fit(development)  # labels from development only

    methods: dict[str, Metrics] = {}
    for name, predictor in (
        ("Always Retry", always),
        ("Rule Based", rules),
        ("ML Only", ml),
    ):
        predictions = [predictor.predict(f) for f in holdout.features]
        methods[name] = score(predictions, holdout.ground_truth)

    methods["KTHMA"] = score(_kthma_predictions(dataset, "holdout"), holdout.ground_truth)
    return EvaluationReport(methods=methods)


def incremental_vs(report: EvaluationReport, method: str) -> float:
    """Additional money KTHMA recovered over a baseline."""
    return report.methods["KTHMA"].revenue_recovered - report.methods[method].revenue_recovered


def format_report(report: EvaluationReport) -> str:
    header = f"{'METHOD':<16}{'RECOVERY':>12}{'WRONG ACTIONS':>16}{'ACTION ACC':>12}"
    lines = [header]
    for name, m in report.methods.items():
        wrong_actions = round(m.false_intervention_rate * m.total_cases)
        lines.append(
            f"{name:<16}{'Rs' + format(m.revenue_recovered, ','):>12}{wrong_actions:>16}{m.action_accuracy:>12.3f}"
        )
    lines.append("")
    lines.append(f"INCREMENTAL (KTHMA vs Rule Based): +Rs{format(incremental_vs(report, 'Rule Based'), ',')}")
    lines.append(f"INCREMENTAL (KTHMA vs Always Retry): +Rs{format(incremental_vs(report, 'Always Retry'), ',')}")
    return "\n".join(lines)
