# KTHMA

**AI revenue recovery for merchants.** Razorpay Buildathon, Track 03: AI Revenue Recovery.

KTHMA finds revenue that is slipping away for a merchant, works out why, decides
what is worth recovering, acts only within defined safety limits, verifies the
outcome, and measures the money actually recovered.

> **Pipeline:** DETECT → DIAGNOSE → DECIDE → ACT → VERIFY → MEASURE

> **One-line pitch:** KTHMA makes more money and makes fewer harmful
> interventions than a plain rules engine — proved on the same untouched
> hold-out cases, not by hand-waving.

---

## Why KTHMA beats a rules engine

A rules engine maps each leakage type to one canned action
(`payment failure → retry`). KTHMA is a **learned value policy**: a random
forest trained on recovery outcomes that picks the action maximizing
expected recovery value **per case**, and learns that **doing nothing** is often
the right call (intelligent refusal, AGENTS.md scenario D).

Hold-out evaluation (1,000 untouched cases, `seed 42` — never invented):

```text
METHOD              RECOVERY   WRONG ACTIONS  ACTION ACC
Always Retry       Rs150,277       200       0.115
Rule Based         Rs623,802        84       0.600
ML Only            Rs610,806        63       0.600
KTHMA            Rs1,055,640        58       0.935

INCREMENTAL (KTHMA vs Rule Based): +Rs431,838
INCREMENTAL (KTHMA vs Always Retry): +Rs905,363
```

KTHMA recovers **+₹431,838 more than the rule baseline** while making **fewer
wrong actions** (58 vs 84). Run it yourself:

```bash
set PYTHONPATH=src&& python -m pytest tests/test_signal.py -q
```

## Demo (one click, deterministic)

```bash
set PYTHONPATH=src&& python -m kthma.demo
```

Prints scenario A–D (payment failure, checkout abandonment, subscription
failure, and a do-nothing refusal), then a **counterfactual**: the same case
where a rules engine gets ₹0 and KTHMA recovers ₹2,499 because it read the
feature interactions (`insufficient_funds + netbanking → payment link`, not
`retry`). This is the whole differentiation, shown on screen one of the
dashboard too.

## Dashboard

```bash
set PYTHONPATH=src&& uvicorn kthma.api:app
```

`GET /` leads with the **KTHMA vs Rules** money + harm comparison, then headline
cards, leakage breakdown, the pipeline funnel ("how we got here"), active
recovery cases you can investigate and approve, and the hold-out evaluation
table.

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

React-less FastAPI + SQLite (SQLAlchemy), scikit-learn policy, Razorpay Test
Mode (labelled Simulator until keys are set, ADR 0003). All data is synthetic,
labelled `DEMO MERCHANT · SYNTHETIC DATA`.

## Layout

```text
src/kthma/
  __init__.py    seeded synthetic generator (learnable signal, hidden ground truth)
  pipeline.py    DETECT → DIAGNOSE → DECIDE → POLICY → ACT → VERIFY
  execution.py   labelled Simulator + Razorpay Test Mode (paid verification)
  recovery_model.py  learned value policy + intelligent refusal
  baselines.py   Always Retry · Rule Based · ML Only
  evaluation.py  scoring seam (action accuracy, harm, Rs recovered)
  report.py      hold-out report, incremental vs baselines, learning loop
  api.py         dashboard + investigation + approve/verify
  demo.py        deterministic demo + counterfactual
```