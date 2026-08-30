"""One-click deterministic demo: at-risk -> investigate -> approve -> recover -> measure."""

from kthma import generate
from kthma.execution import GroundedSimulatorExecutor
from kthma.models import SplitDataset
from kthma.pipeline import CaseReport, run_case


def _pick(dataset: SplitDataset, leakage_type: str, failure_reason: str | None = None):
    for f in dataset.development.features:
        if f.leakage_type == leakage_type and (failure_reason is None or f.failure_reason == failure_reason):
            return f
    for f in dataset.holdout.features:
        if f.leakage_type == leakage_type and (failure_reason is None or f.failure_reason == failure_reason):
            return f
    raise LookupError(f"no case for {leakage_type}")


def _pick_scenario_a(dataset: SplitDataset, world: dict[str, bool]):
    """AGENTS.md scenario A: Rs2,499, bank timeout, high intent, recoverable.
    Pinning may consult ground truth (demo selection, outside the pipeline);
    the pipeline itself never sees it."""
    candidates = [
        f
        for f in (*dataset.development.features, *dataset.holdout.features)
        if f.leakage_type == "payment_failure"
        and f.failure_reason == "bank_timeout"
        and f.amount == 2499
        and f.prior_successful_payments >= 3
        and world.get(f.recovery_case_id, (False, ""))[0]
    ]
    if candidates:
        return candidates[0]
    return _pick(dataset, "payment_failure", "bank_timeout")


def run_demo(seed: int = 42) -> str:
    dataset = generate(seed=seed, n=1000)  # large enough to pin all four scenarios
    world = {
        g.recovery_case_id: (g.recoverable, g.best_action)
        for g in (*dataset.development.ground_truth, *dataset.holdout.ground_truth)
    }
    executor = GroundedSimulatorExecutor(world)

    lines = ["KTHMA DEMO · DEMO MERCHANT · SYNTHETIC DATA", ""]
    scenarios = [
        ("A - Payment failure", _pick_scenario_a(dataset, world)),
        ("B - Checkout abandonment", _pick(dataset, "checkout_abandonment")),
        ("C - Subscription failure", _pick(dataset, "subscription_failure")),
        ("D - Do nothing (intelligent refusal)", _pick(dataset, "repeated_failure")),
    ]

    total_at_risk = 0
    total_recovered = 0
    for title, features in scenarios:
        report = run_case(features, executor)
        total_at_risk += report.detection.revenue_at_risk
        total_recovered += report.verification.recovered_amount
        lines.append(f"{title}: Rs{report.detection.revenue_at_risk} at risk")
        for step in report.timeline:
            lines.append(f"  [{step.stage}] {step.detail}")
        lines.append("")

    lines.append(f"Revenue at risk: Rs{total_at_risk}")
    lines.append(f"Revenue recovered: Rs{total_recovered}")
    return "\n".join(lines)


def main() -> int:
    print(run_demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
