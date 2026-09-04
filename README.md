# KTHMA

**AI revenue recovery for merchants.** Razorpay Buildathon, Track 03: AI Revenue Recovery.

KTHMA finds revenue that is slipping away for a merchant, works out why, decides
what is worth recovering, acts only within defined safety limits, verifies the
outcome, and measures the money actually recovered.

> **Pipeline:** DETECT → DIAGNOSE → DECIDE → POLICY → ACT → VERIFY → MEASURE

> **One-line pitch:** KTHMA makes more money and makes fewer harmful
> interventions than a plain rules engine — proved on the same untouched
> hold-out cases, not by hand-waving.

> **Safety contract:** GET endpoints only *plan* cases. No money-moving action
> runs until an operator explicitly approves it via `POST /approve`. Every
> approved execution is persisted to a SQLite audit trail.

---

## Why KTHMA beats a rules engine

A rules engine maps each leakage type to one canned action
(`payment failure → retry`). KTHMA is a **learned value policy**: a random
forest trained on recovery outcomes that picks the action maximizing
expected recovery value **per case**, and learns that **doing nothing** is often
the right call (intelligent refusal, AGENTS.md scenario D).

Hold-out evaluation (1,000 untouched cases, `seed 42`, `n=5000` — never invented):

```text
METHOD              RECOVERY     WRONG ACTIONS  ACTION ACC
Always Retry       Rs3,424,129       310       0.690
Rule Based         Rs3,424,129       242       0.690
ML Only            Rs3,424,129       242       0.690
KTHMA              Rs4,930,575       121       0.963

INCREMENTAL (KTHMA vs Rule Based): +Rs1,506,446
INCREMENTAL (KTHMA vs Always Retry): +Rs1,506,446
```

KTHMA recovers **+₹1,506,446 more than the rule baseline** while making **half
the wrong actions** (121 vs 242). Run it yourself:

```bash
python -m pytest tests/test_signal.py -q
```

## Demo (one click, deterministic)

```bash
python -m kthma.demo
```

Prints scenario A–D (payment failure, checkout abandonment, subscription
failure, and a do-nothing refusal), then a **counterfactual**: the same case
where a rules engine gets ₹0 and KTHMA recovers ₹2,499 because it read the
feature interactions (`insufficient_funds + netbanking → payment link`, not
`retry`). This is the whole differentiation, shown on screen one of the
dashboard too.

## Dashboard

```bash
uvicorn kthma.api:app
```

`GET /` leads with the **KTHMA vs Rules** money + harm comparison, then headline
cards, leakage breakdown, the pipeline funnel ("how we got here"), active
recovery cases you can investigate and approve, and the hold-out evaluation
table.

**Operator-in-the-loop:** the dashboard shows *planned* state on load. Clicking
"Approve & Execute" on a case is the only way a money-moving action runs, and
the result is saved to the audit trail. A second approve on the same case
returns the stored result without executing again (idempotent).

## Evaluation

Fit on the development split, score on the untouched hold-out. The system never
sees hold-out labels at train or tune time.

```text
Baselines: Always Retry · Rule Based · ML Only — compared with KTHMA
```

Every money action is **explainable, bounded, auditable, and verified**:
low-risk actions auto-execute, medium/high-risk require approval, actions above
a hard cap are refused, and a real Razorpay payment link only counts as
recovered after `paid` verification.

## Stack

FastAPI + SQLite (SQLAlchemy), scikit-learn policy, Razorpay Test
Mode (labelled Simulator until keys are set, ADR 0003). All data is synthetic,
labelled `DEMO MERCHANT · SYNTHETIC DATA`.

## Layout

```text
src/kthma/
  __init__.py    seeded synthetic generator (learnable signal, hidden ground truth)
  pipeline.py    DETECT → DIAGNOSE → DECIDE → POLICY → ACT → VERIFY (+ plan_case)
  execution.py   labelled Simulator + Razorpay Test Mode (paid verification)
  recovery_model.py  learned value policy + intelligent refusal
  baselines.py   Always Retry · Rule Based · ML Only
  evaluation.py  scoring seam (action accuracy, harm, Rs recovered)
  report.py      hold-out report, incremental vs baselines, learning loop
  store.py       SQLite persistence (features, ground truth, executions audit trail)
  api.py         dashboard + investigation + approve/verify
  demo.py        deterministic demo + counterfactual
```