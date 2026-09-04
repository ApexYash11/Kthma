"""Evaluation report: fit on development, score on hold-out (never tuned on it)."""

from __future__ import annotations

from dataclasses import dataclass

from kthma.baselines import AlwaysRetryBaseline, MLOnlyBaseline, RuleBasedBaseline
from kthma.evaluation import Metrics, Prediction, score
from kthma.models import Split, SplitDataset
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


def learning_loop(
    dataset: SplitDataset,
    train_sizes: tuple[float, ...] = (0.25, 0.5, 1.0),
    seed: int = 42,
) -> list[dict]:
    """KTHMA improves with feedback.

    The working learning loop: the policy is fit on an increasing fraction of
    development outcomes (as if recovery outcomes were logged and fed back),
    and scored on the untouched hold-out each time. The last row is the same
    model `run_evaluation` uses; the curve shows re-training from outcomes
    visibly lifts hold-out performance.
    """
    dev_features = list(dataset.development.features)
    dev_truth = list(dataset.development.ground_truth)
    n = len(dev_features)
    results: list[dict] = []
    for frac in train_sizes:
        k = max(20, int(round(n * frac)))
        k = min(k, n)
        split = Split(features=tuple(dev_features[:k]), ground_truth=tuple(dev_truth[:k]))
        policy = fit_policy(split, seed=seed)
        predictions = [
            Prediction(
                recovery_case_id=f.recovery_case_id,
                recoverable=decide(f, policy).action != "do_nothing",
                action=decide(f, policy).action,
            )
            for f in dataset.holdout.features
        ]
        m = score(predictions, dataset.holdout.ground_truth)
        results.append(
            {
                "n_train": k,
                "action_accuracy": m.action_accuracy,
                "revenue_recovered": m.revenue_recovered,
                "false_intervention_rate": m.false_intervention_rate,
            }
        )
    return results


def format_report(report: EvaluationReport) -> str:
    header = f"{'METHOD':<16}{'RECOVERY':>14}{'WRONG ACTIONS':>16}{'ACTION ACC':>12}"
    lines = [header]
    for name, m in report.methods.items():
        # True wrong actions: false interventions (acted when should not have)
        # plus misses (did not act when should have). This is total_cases minus
        # correct decisions, not a rate multiplied by total.
        wrong_actions = m.total_cases - round(m.action_accuracy * m.total_cases)
        lines.append(
            f"{name:<16}{'Rs' + format(m.revenue_recovered, ','):>14}{wrong_actions:>16}{m.action_accuracy:>12.3f}"
        )
    lines.append("")
    lines.append(f"INCREMENTAL (KTHMA vs Rule Based): +Rs{format(incremental_vs(report, 'Rule Based'), ',')}")
    lines.append(f"INCREMENTAL (KTHMA vs Always Retry): +Rs{format(incremental_vs(report, 'Always Retry'), ',')}")
    return "\n".join(lines)
