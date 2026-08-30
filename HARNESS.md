# KTHMA — prompt for another harness

Paste this as the first message in a new agent/IDE. Then work in this repo. Do not restart the product from scratch.

You are the coding agent for **KTHMA** (Razorpay Buildathon Track 03: AI Revenue Recovery). Product name is KTHMA, not RevPilot.

Read these before writing code, in this order:

1. `CONTEXT.md` — vocabulary. Use those terms only.
2. `docs/adr/` — accepted decisions. Do not reopen them.
3. `AGENTS.md` — product, phases, quality bar.
4. `.scratch/synthetic-data/spec.md` — Phase 2 spec.
5. `.scratch/synthetic-data/issues/` — tickets.

If a skill in `.agents/skills/` matches the task (`tdd`, `diagnosing-bugs`, `code-review`, `research`), follow it.

---

## How to develop

**working product > architecture complexity > visual polish**

- One ticket at a time. TDD: failing test first, watch it fail, then minimal code. Test only at the agreed seam.
- Smallest working version. Run tests. Fix. Then next ticket.
- No fake metrics, fake Razorpay calls, or fake reasoning.
- No generic chatbot UI.
- No LLM / Razorpay / ML / frontend until the current ticket asks for them.
- At the end of a phase, report: COMPLETED / TESTED / METRICS / KNOWN ISSUES / NEXT STEP.

Seam for Phase 2:

`generate(seed, n, config) -> SplitDataset`

Features and ground truth are separate. Ground truth: `recoverable`, `best_action`, `expected_outcome`, `amount`. Those fields must not appear on features.

---

## Locked (do not re-grill)

| Decision | Where |
|---|---|
| Demo-first. Generator can emit 4000+1000 from day one. First eval may be smaller. | ADR 0001 |
| SQLite + SQLAlchemy | ADR 0002 |
| Razorpay path = labelled Simulator until Test Mode keys exist | ADR 0003 |
| No custom SMS/email | ADR 0004 |
| OpenRouter behind a swappable port. Model via env. Fail closed. | ADR 0005 |
| LLM only at Diagnosis, Decision, Why. Everything else is code. | ADR 0006 |
| One demo merchant. Operator = merchant ops. No auth. Banner: `DEMO MERCHANT · SYNTHETIC DATA` | AGENTS.md |

Pipeline: DETECT → DIAGNOSE → DECIDE → ACT → VERIFY → MEASURE

Scenarios: payment failure, checkout abandonment, subscription failure, do-nothing.

---

## Where the work is

Phase 1 (spec + decisions): done.

Phase 2: **done.** All four tickets complete, 20/20 tests green. `--rows 5000 --seed 42` yields 4000 / 1000 with zero ID overlap.

Run the generator:

```bash
set PYTHONPATH=src&& python -m kthma.cli --rows 5000 --seed 42 --db dataset.sqlite3
```

---

## Status after phases 3-8 (all committed)

Phases 3-8 are built and tested.

- Phase 3: `src/kthma/baselines.py` (always-retry, rule-based, ML-only) + `src/kthma/evaluation.py` scoring seam.
- Phase 4: `src/kthma/pipeline.py` (DETECT/DIAGNOSE/DECIDE/POLICY/ACT/VERIFY, typed contracts) + `src/kthma/execution.py` (labelled Simulator, fail-closed Razorpay, grounded simulator).
- Phase 5: `src/kthma/report.py` — fit on development, score on hold-out; Always Retry / Rule Based / ML Only / KTHMA.
- Phase 6: `docs/research/razorpay-test-mode.md` — verified Payment Links API facts (paise, +30-link Test Mode cap, lifecycle); executor fails closed without keys.
- Phase 7: `src/kthma/api.py` — FastAPI + dashboard at `/` with the synthetic-data banner; `uvicorn kthma.api:app`.
- Phase 8: `python -m kthma.demo` — deterministic scenarios A-D, one-click, ends with revenue recovered.

## Differentiation work (strategy MVP, committed)

Per `docs/strategy-assessment.md`, KTHMA is now a **learned value policy**, not a rules engine.

- `__init__.py`: the generator now derives recoverable/best_action from context (latent account health + feature interactions + noise), so the labels are **learnable**. Documented in `_resolve_outcome`.
- `src/kthma/recovery_model.py`: `fit_policy` trains a random forest on development features only; `RecoveryPolicy.predict` returns (best_action, probability); learnable **intelligent refusal** (do_nothing is a class).
- `pipeline.decide(features, policy=None)`: uses the learned policy when provided, else a rule default (cold-start / unit tests).
- `report.run_evaluation`: KTHMA predicts via a policy fit on development only. `format_report` prints INCREMENTAL vs baselines.

### The whole point (same 1,000 hold-out cases, seed 42)

```text
METHOD              RECOVERY   WRONG ACTIONS  ACTION ACC
Always Retry       Rs150,277             200       0.115
Rule Based         Rs623,802              84       0.600
ML Only            Rs610,806              63       0.600
KTHMA            Rs1,055,640              58       0.935

INCREMENTAL (KTHMA vs Rule Based): +Rs431,838
INCREMENTAL (KTHMA vs Always Retry): +Rs905,363
```

KTHMA **beats** the rule baseline by +Rs431,838 recovered at 0.935 vs 0.600 action accuracy with fewer false interventions. Before this work all four methods tied exactly.

## Phase close-out

```text
COMPLETED
  Phases 2-8, plus the differentiation MVP: signal-bearing generator and a
  learned value policy that provably beats the rule baseline on hold-out.

TESTED
  python -m pytest tests/ -q  (test_signal run per-test; RF fits are seconds-scale)

METRICS (hold-out, seed 42 — never invented)
  KTHMA 0.935 action acc, Rs1,055,640 recovered, 58 wrong actions
  vs Rule Based 0.600 / Rs623,802 / 84;  vs Always Retry 0.115 / Rs150,277 / 200
  Incremental: +Rs431,838 vs rules, +Rs905,363 vs always-retry.

KNOWN ISSUES
  - Razorpay API specifics partially verified; Execution stays Simulator unless
    KTHMA_EXECUTOR=razorpay with keys set (ADR 0003).
  - Dashboard leads with headline cards, not yet the counterfactual-first hook
    (strategy item 7) — next slice.
  - random forest fits take seconds; some heavy tests must run individually.
  - CLI/Demo need PYTHONPATH=src (package not pip-installed).

NEXT STEP
  Dashboard counterfactual-first hook (KTHMA vs rules on screen one), README,
  then optional Razorpay `paid` verification on the demo path.
```

Razorpay research file now verified (see `docs/research/razorpay-test-mode.md`). Until Test Mode keys exist, Execution stays a labelled Simulator. `docs/strategy-assessment.md` is the product plan.

---

## Done looks like (Ticket 1)

```text
python -m pytest tests/test_generate.py -v
```

All green. Ticket `01-in-memory-generate.md` checkboxes ticked. Features still have zero ground-truth fields. Then Ticket 2.
