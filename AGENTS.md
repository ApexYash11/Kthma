# KTHMA

You are the lead engineer, product architect, AI engineer, and hackathon strategist for this repo.

We are building **KTHMA** for the Razorpay Buildathon, **Track 03: AI Revenue Recovery**.

Read `CONTEXT.md` before naming anything. Use those terms. Do not invent synonyms.

If you are a **new harness / new chat** continuing this repo, start from `HARNESS.md` (current ticket, locked ADRs, how to develop). This file is the full product spec.

## How we work

Goal: ship a working product with little AI slop. Decisions first, then small slices, then evidence.

| Situation | Do this |
|---|---|
| Product/architecture decision | `grill-with-docs`. Do not also run Superpowers brainstorming on the same decision. |
| Last message did not land | `wait-what` |
| Razorpay / API facts | `research` against official docs. Do not guess APIs. |
| Ready to build a slice | `to-spec` then `to-tickets` then `implement` with `tdd` at agreed seams |
| Hard bug | `diagnosing-bugs` |
| After a slice | `code-review` |
| Agent module shape | `codebase-design` (deep modules, typed contracts, real seams) |

Do not start by writing thousands of lines. At every phase: explain what you are building, show the files, implement the smallest working version, run tests, verify, fix, then move on.

If a feature is not needed for the core demo, defer it.

**working product > architecture complexity > visual polish**

Do not install or invoke pstack unless the user asks for browser QA of the dashboard.

### Voice

Direct. Concrete. Name the file, the function, the command. No filler, no consultant tone.

No fake metrics. No fake Razorpay calls. No fake reasoning. No generic chatbot UI.

End with what to do next.

### Phase close-out

At the end of each phase, report:

```text
COMPLETED
TESTED
METRICS
KNOWN ISSUES
NEXT STEP
```

## Agent skills

### Issue tracker

Local markdown under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `CONTEXT.md` at repo root, ADRs in `docs/adr/`. See `docs/agents/domain.md`.

### Skills in this repo

Installed under `.agents/skills/` from [mattpocock/skills](https://github.com/mattpocock/skills), subset only.

User-invoked: `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `wait-what`

Model-invoked when they fit: `grilling`, `domain-modeling`, `tdd`, `codebase-design`, `research`, `code-review`, `diagnosing-bugs`, `writing-for-agents`

---

## 1. Product

KTHMA is an AI-powered revenue recovery system for merchants.

Pipeline:

**DETECT → DIAGNOSE → DECIDE → ACT → VERIFY → MEASURE**

Identify revenue slipping away, understand why, choose the safest/highest-value recovery action, execute it in a controlled environment, verify the outcome, and calculate how much revenue was recovered.

This must not feel like a generic AI chatbot.

Core experience:

> You have ₹X revenue at risk. Here are the causes. Here are the customers/transactions we can recover. Here is the best action for each one. We executed the safe actions and recovered ₹Y.

---

## 2. No real merchant data

We do not have real merchant production data. Do not pretend synthetic data is real.

Build a realistic **synthetic merchant dataset** with known ground truth.

Dashboard label:

**DEMO MERCHANT · SYNTHETIC DATA**

Use Razorpay Test Mode APIs where appropriate to demonstrate real payment workflow execution.

Synthetic dataset must include realistic: payments, payment attempts, payment methods, customers, checkout sessions, subscriptions, failure reasons, timestamps, retry history, customer history, transaction outcomes.

Create controlled scenarios where we know:

- whether revenue was recoverable
- the best recovery action
- expected outcome
- actual simulated outcome

Ground truth must stay hidden from the model during prediction.

---

## 3. Core scenarios (build these first)

**A — Payment failure.** ₹2,499, bank timeout, high purchase intent, high recovery probability → retry/payment link → succeed → ₹2,499 recovered.

**B — Checkout abandonment.** ₹8,999, entered payment flow then abandoned, high intent → payment link better than repeated retry → customer completes.

**C — Subscription failure.** ₹1,299 recurring failed, historically paid successfully → retry + reminder → verify.

**D — Do nothing.** Multiple recent failures, low recovery probability, repeated attempts. System must say: do not retry. Escalate or stop.

Scenario D matters: intelligent refusal, not blind recovery.

---

## 4. Agent architecture

Focused modules with typed input/output contracts. Not one giant agent. Not seven LLMs passing prose.

Each stage is a **module** behind a small interface. Prefer deterministic code + structured LLM calls at the seams that actually need judgment. Hide complexity inside the module.

### Detection

Finds leakage: failed payments, checkout abandonment, subscription failures, repeated failures, unusual degradation.

```json
{
  "revenue_at_risk": 4999,
  "recoverable": true,
  "reason": "payment_timeout"
}
```

### Diagnosis

Why it was lost. Output: root cause, evidence, confidence, recovery opportunity.

### Recovery decision

Chooses the action: retry payment, generate payment link, send reminder, suggest alternate payment method, retry subscription, escalate to human, do nothing.

Optimize expected recovery value: `amount × probability_of_success`, not probability alone.

### Policy / safety (mandatory)

```text
LOW RISK → automatically execute
MEDIUM RISK → require approval
HIGH RISK / MONEY-MOVING → require explicit approval
```

Never let the LLM perform unrestricted money-moving actions.

### Execution

Runs only approved actions through a controlled tool layer: create payment link, retry payment, send notification, retry subscription, record recovery action. Default adapter is the labelled Simulator until Razorpay Test Mode keys exist (ADR 0003). No custom email/SMS (ADR 0004).

### Verification

Did payment succeed? Did revenue recover? Did the action fail? Another action? Escalate?

### Evaluation

Hackathon evaluation system. Compare predicted decisions against hidden synthetic ground truth: precision, recall, action accuracy, recovery rate, revenue recovered, false intervention rate.

---

## 5. Evaluation is a first-class feature

Do not claim the AI works. Measure it.

```text
5000 synthetic transactions
4000 development/test-development records
1000 hidden hold-out records
```

The system must not see ground-truth labels for the hold-out set.

Baselines:

1. Always retry failed payments
2. Simple rule-based recovery (`IF timeout THEN retry`)
3. ML-only recovery prediction

Final system: ML + agents + policy + execution + verification.

Dashboard comparison (numbers from actual test data, never invented):

```text
METHOD             RECOVERY     WRONG ACTIONS
Always Retry       ₹X           X
Rule Based         ₹X           X
ML Only            ₹X           X
KTHMA              ₹X           X
```

---

## 6. Metrics

**Detection:** precision, recall, F1

**Decision:** action accuracy, recovery precision, false intervention rate

**Business:** revenue at risk, recoverable revenue, revenue recovered, recovery rate, expected recovery value

**Operational:** agent execution success rate, average investigation time, automatic interventions, human approvals

Headline metric: **₹ recovered**

---

## 7. Dashboard

Polished fintech operations dashboard. Brand: **KTHMA**. No auth. Persistent banner: **DEMO MERCHANT · SYNTHETIC DATA**.

Main screen: Revenue Processed, Revenue At Risk, Recoverable, Recovered, Recovery Rate.

Then: leakage breakdown (payment failures, checkout abandonment, subscription failures, other) and active recovery cases.

Each case: amount, type, root cause, recovery probability, recommended action, expected recovery, Investigate.

---

## 8. Investigation screen

Opening a case shows the agent timeline with timestamps. Every important decision has evidence. Example shape: Detection found leakage → Diagnosis named the cause → customer history → Recovery estimated probability → Policy permitted → Execution ran → Verification confirmed → ₹ recovered.

---

## 9. "Why?" functionality

Every recommendation must be explainable. Concise evidence and decision factors. Do not expose hidden chain-of-thought.

---

## 10. Data generation

Reproducible synthetic-data generator: random seed, configurable transaction count and failure rates, known ground truth, realistic customer and payment behavior.

```bash
python generate_data.py --rows 5000 --seed 42
```

Ground truth stored separately from model-visible features. Hold-out labels must not leak into agents.

---

## 11. Stack

Keep it small enough to finish.

- Frontend: React, TypeScript, Tailwind CSS
- Backend: Python, FastAPI
- Database: SQLite + SQLAlchemy (ADR 0002). Postgres later only if we need it.
- AI: OpenRouter behind a swappable interface. Model via env vars. Fail closed if key or model is missing (ADR 0005). LLM only at Diagnosis, Decision, Why (ADR 0006).
- ML: scikit-learn or LightGBM if useful
- Payments: Razorpay Test Mode where applicable
- Testing: pytest, API tests, agent tests, evaluation tests

Do not introduce unnecessary technologies.

---

## 12. Phases

Do not build everything at once.

**Phase 1 — Specification.** Inspect repo, skills, Razorpay Test Mode docs. Identify what can execute vs must simulate. Concise plan. Risks. Do not assume APIs. Do not start the frontend.

**Phase 2 — Data.** Generator, ground truth, dev/test split, evaluation dataset. Verify statistically.

**Phase 3 — Baseline.** Always-retry, rule-based, simple ML. Run evaluation.

**Phase 4 — Agent system.** Detection → Diagnosis → Decision → Policy → Execution → Verification. Clear I/O contracts.

**Phase 5 — Evaluation.** Hold-out only. Do not tune against it. Real report.

**Phase 6 — Razorpay Test Mode.** Safe execution path. If an API cannot be used, a labelled simulator, not a fake API call.

**Phase 7 — Dashboard.** Only after backend workflow works. UI around actual data and APIs.

**Phase 8 — Demo mode.** Deterministic, one-click, repeatable: revenue at risk → investigation → recommendation → approval → action → successful recovery → ₹ recovered.

---

## 13. Hackathon demo (~3 minutes)

Open with ₹ revenue at risk. Investigate a failed payment. Show why. Recommend retry with expected recovery. Policy approves. Execute in test mode/simulator. Verification succeeds. Dashboard updates ₹ recovered. Run batch evaluation (recovery rate, precision, recall, action accuracy, revenue recovered).

Final line:

> KTHMA doesn't just find lost revenue. It decides what is worth recovering, acts within defined limits, verifies the outcome, and measures the money recovered.

---

## 14. Do not build

- generic chatbot
- generic payment dashboard
- fake AI reasoning
- fake metrics
- fake Razorpay API calls
- unrestricted autonomous payment actions
- unnecessary multi-agent complexity
- 20 agents that only pass text between each other

Every component must have a purpose.

---

## 15. Engineering quality

Typed interfaces, structured agent outputs, validation, retries, idempotency, logging, audit trail, error handling, deterministic demo data, automated tests.

Every money-related action must be:

**explainable + bounded + auditable + reversible where possible.**
