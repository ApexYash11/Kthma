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

Next phase: Phase 3 baselines (always-retry, rule-based, ML-only) run against the persisted development set. Do not start the frontend.

Razorpay research file was never written. If you need execute-vs-simulate facts, research official Razorpay docs into `docs/research/razorpay-test-mode.md`. Until Test Mode keys exist, Execution stays a labelled Simulator.

---

## Done looks like (Ticket 1)

```text
python -m pytest tests/test_generate.py -v
```

All green. Ticket `01-in-memory-generate.md` checkboxes ticked. Features still have zero ground-truth fields. Then Ticket 2.
