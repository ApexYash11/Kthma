# Phase 2: Synthetic dataset

**Status:** ready-for-agent

**Parent:** KTHMA Phase 2 (ADR 0001)

## Problem Statement

KTHMA has no real merchant data. Evaluation, Detection, and the demo all need a realistic synthetic merchant dataset with hidden ground truth. Without a reproducible generator and a leak-proof split, later phases will invent numbers or accidentally train on labels.

## Solution

A seeded generator that emits recovery-case rows for one demo merchant. Model-visible features and ground truth are separate. The same split rules produce a development set and a hold-out set at any size, including the full 4000 + 1000. A stats check proves the dataset is well-formed. First eval runs may be smaller; the generator can still emit 5000.

## User Stories

1. As an operator, I want the dashboard to be able to show leakage from synthetic data, so that the demo is honest about DEMO MERCHANT · SYNTHETIC DATA.
2. As an operator, I want recovery cases covering payment failure, checkout abandonment, subscription failure, and do-nothing, so that the product demonstrates judgment not blind retry.
3. As an engineer, I want `generate` with a seed to be bit-for-bit reproducible, so that the 3-minute demo and eval can be rerun.
4. As an engineer, I want row count to be configurable, so that I can run a small eval now and 5000 later without changing code.
5. As an engineer, I want n=5000 to yield 4000 development rows and 1000 hold-out rows, so that ADR 0001 holds.
6. As an engineer, I want a smaller n to use the same 80/20 split rule, so that small runs are not a different product.
7. As Evaluation, I want hold-out ground truth that the pipeline never sees at train or tune time, so that reported ₹ recovered is real.
8. As Detection, I want only model-visible features, so that I cannot read recoverable or best recovery action.
9. As Diagnosis, I want evidence fields (failure reason, retry history, customer history) without labels, so that judgment is over evidence.
10. As Decision, I want amounts and history features without expected recovery value labels, so that expected recovery value is computed not copied.
11. As Evaluation, I want hidden labels: recoverable, best recovery action, expected outcome, so that I can score action accuracy and ₹ recovered.
12. As an engineer, I want ground truth stored separately from the feature table, so that a join cannot happen by accident in Detection.
13. As an engineer, I want no overlapping recovery-case IDs between development and hold-out, so that leakage across the split is impossible.
14. As an engineer, I want failure rates to be configurable, so that scenarios can be stressed without rewriting the generator.
15. As an engineer, I want realistic payments, attempts, methods, customers, timestamps, retry history, and outcomes, so that the demo does not look like random noise.
16. As an engineer, I want at least one recovery case of each leakage type A–D in every generated set above a documented minimum n, so that demo mode is not empty.
17. As an engineer, I want a stats report after generation, so that I can verify counts, rates, and split integrity without eyeballing CSV.
18. As Evaluation, I want development labels available for baseline fitting, so that ML-only can train without touching hold-out.
19. As Evaluation, I want hold-out features without labels in the same store Detection would see, so that scoring is the only consumer of hold-out ground truth.
20. As an operator, I want amounts in INR rupees, so that ₹ recovered matches the dashboard language.
21. As an engineer, I want idempotent generation for the same seed and n, so that tests do not flake.
22. As an engineer, I want the generator to run with no LLM and no Razorpay keys, so that Phase 2 does not depend on OpenRouter or Test Mode.
23. As Policy, I want enough history on a do-nothing case (repeated failures, low recoverability) that a later rule can refuse retry, so that scenario D is in the data not just the prompt.
24. As an engineer, I want a single public generate call, so that there is one seam to test.

## Implementation Decisions

- One module: Dataset generator. Public seam is `generate(seed, n, failure_rate config) -> SplitDataset`. No other public surface for Phase 2.
- `SplitDataset` contains: development features, development ground truth, hold-out features, hold-out ground truth, and a stats snapshot. Features and ground truth are different structures. They share a recovery-case ID for Evaluation only.
- Split rule: after generation, shuffle with the seed, then 80% development / 20% hold-out. n=5000 => 4000 / 1000. Remainder from integer division goes to development.
- Minimum n for “all four leakage types present”: 20. Below that, generation still works but the stats report flags missing leakage types.
- Model-visible feature fields (conceptual): recovery-case ID, leakage type, amount, currency INR, payment method, failure reason, attempt count, last attempt timestamp, customer ID, prior successful payments count, prior failures count, days since last success, subscription flag, checkout-entered flag. No recoverable flag, no best action, no expected outcome, no generating probability used as a label.
- Ground truth fields (conceptual): recovery-case ID, recoverable, best recovery action (one of the glossary recovery actions), expected outcome (recovered amount or zero), intended scenario tag (A/B/C/D) for demo pinning.
- Best recovery action is assigned from scenario rules in the generator (timeout + high intent → retry or payment link; abandonment → payment link; subscription fail with history → retry subscription; repeated failures → do nothing). This is how we know the answer. Detection never receives it.
- Persistence: SQLite via SQLAlchemy (ADR 0002). Two tables or two stores: features vs ground_truth. Hold-out ground truth is not loaded by Detection.
- CLI: seed, rows, optional failure-rate flags. Default seed documented. Must support `--rows 5000 --seed 42`.
- No LLM. No Razorpay. No dashboard. SQLite file path configurable; tests use an isolated file.
- Stats snapshot: row counts by split, counts by leakage type, configured vs realized failure rate, ID overlap (must be zero), feature columns that must not exist (label names), presence of scenarios A–D.

## Testing Decisions

- Test only through `generate`. Do not test private sampling helpers.
- Same seed + n + config => identical recovery-case IDs, amounts, leakage types, and labels.
- Feature structures contain none of: recoverable, best recovery action, expected outcome, intended scenario tag.
- Hold-out IDs ∩ development IDs = empty.
- n=5000 => 4000 development, 1000 hold-out.
- n=100 => 80 / 20 under the same rule.
- n>=20 => at least one of each leakage type.
- Stats report fails (or returns a clear error flag) if label columns leaked into features or IDs overlap.
- Generator runs with no network and no env keys.
- No prior tests in this repo; these are the first. Keep them behavior tests on `generate`, not snapshots of full dumps.

## Out of Scope

- Detection, Diagnosis, Decision, Policy, Execution, Verification, Evaluation scoring
- OpenRouter / LLM
- Razorpay Test Mode and Simulator execution
- Dashboard and auth
- Baselines (Phase 3)
- Demo one-click runner (Phase 8), except the generator must be able to pin scenarios A–D via seed so demo can use it later

## Further Notes

- Glossary: recovery case, leakage, ground truth, hold-out, demo merchant, synthetic data. Checkout abandonment is our leakage type, not a Razorpay object.
- Razorpay execute-vs-simulate research is not required to finish this spec. Execution stays Simulator until Test Mode keys exist (ADR 0003).
- First eval size is a later phase choice. This phase only guarantees the generator can emit the full split.
