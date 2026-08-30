# KTHMA — Competitive Strategic Assessment

*Internal strategy memo. Razorpay Buildathon, Track 03: AI Revenue Recovery.*
*Scope: honest product/AI evaluation, differentiator, redesign, evaluation, demo.*

---

## 1. Current architecture summary (what it actually does)

A deterministic, rule-driven Python package (FastAPI + SQLAlchemy + a seeded synthetic generator). 65 tests pass.

### 1.1 The honest functional map

| Stage | What it actually is today |
|---|---|
| **Generator** | Seeded synthetic rows. **Knows little** — see §1.3. |
| **Feature model** | 14 fields: amount, leakage_type, payment_method, failure_reason, attempt_count, prior_failures, prior_successes, days_since_last_success, subscription/checkout flags, customer_id, timestamp. |
| **Ground truth** | `recoverable`, `best_action`, `expected_outcome`, `amount`, `intended_scenario`. Stored separately from features. **Correct separation.** |
| **Detection** | `return revenue_at_risk = amount`. It doesn't detect anything — it reads a pre-tagged field. |
| **Diagnosis** | Hardcoded `if/elif` maps leakage_type/failure_reason → canned string (`"bank_timeout_high_purchase_intent"`). No inference. |
| **Decision** | Hardcoded `if/elif` on leakage_type. Pure rule table. |
| **Probability** | A fixed linear formula. No learning, no uncertainty. |
| **Expected recovery value** | `amount × p`. Computed correctly, but cosmetic. |
| **Policy gate** | Anything that isn't `do_nothing` → `"medium", approval required`. No auto tier, no hard-blocked tier. |
| **Execution** | Labelled `SimulatorExecutor` (default) or `HybridRazorpayExecutor` (payment-links → real Test Mode API, retries/subscriptions → simulator). |
| **Verification** | Simulator returns success iff the synthetic world says recoverable AND action == best action. Honest, but simulated. |
| **Baselines** | Always-retry, rule-based, and a tiny pure-Python logistic regression on `recoverable`. |
| **Evaluation** | Scores action-accuracy, false-intervention-rate, ₹ recovered on hold-out. Development for fitting. |
| **Razorpay** | Payment Links **can** reach Test Mode behind a transport seam. Default demo does NOT use it. No webhook/poll verification. |

### 1.2 External gaps

- **No `README.md` exists** at the repo root.
- No architecture doc articulating differentiation.
- No "how a judge should use this" narrative.
### 1.3 The fatal structural fact

Generator logic (src/kthma/__init__.py):

```python
recoverable = rng.random() < 0.95 and leakage_type != "repeated_failure"
best_action = rng.choice(action_pool)      # coin flip
if recoverable: expected_outcome = amount
```

- **`best_action` for a payment failure is a coin flip** between `retry_payment` and `payment_link`.
_Scored as a judge across ~200 submissions._

| Dimension | /10 | Why |
|---|---|---|
| Problem relevance | **8** | AI revenue recovery is a real, well-scoped Track 03 fit. |
| Novelty | **4** | "Agent pipeline" is generic. Nothing here is surprising. |
| AI depth | **2** | No component needs AI. All judgment is if/else. Labels are noise. |
| Technical sophistication | **6** | Clean typed dataclasses, seam design, honest simulator, 65 tests. |
| Razorpay integration | **4** | One real endpoint (payment links) reachable; demo doesn't use it; no verification loop. |
| Revenue impact | **4** | Shows ₹ recovered but with *zero* differentiation from rules. |
| Evaluation quality | **6** | Leak-proof split, reproducible. But it measures nothing meaningful (KTHMA≡rules). |
| Safety | **7** | Policy gate + labelled simulator + fail-closed Razorpay. Good instincts. |
| Explainability | **6** | Timeline + Why exists. But "Why" is a canned string, not reasoning. |
| Product UX | **5** | Dashboard is decent but first screen isn't a hook; no README. |
| Demo wow factor | **3** | Four scenarios are scripted; none shows an AI beat a rule. |
| Feasibility | **8** | Small, buildable, works. |
| Differentiation | **2** | Indistinguishable from a homework rules engine. |

**Composite ≈ 4.6/10 — upper-middle of a field, not a finalist.**

### Why a judge would NOT pick this

- **"It's a rules engine wearing an agent costume."** Every judgment is hardcoded; nothing changes if the AI were deleted.
- **The leaderboard proves it** — KTHMA ties Rule-Based and ML-Only exactly.
- **The data has no signal**, so "learning" and "evaluation" are theater: you can't demonstrate intelligence on noise.
- **No human hook** — no README, first screen is a generic dashboard, demo is scenario-scripted with no counterfactual.
- **No money increments** — never says "KTHMA recovered ₹X MORE than a sane baseline while refusing Y harmful retries."
- **`recoverable` is essentially `95% yes`** (a coin weighted toward yes).

Consequences:

- There is **no learnable signal**. No feature predicts the label better than random for the most important action choice.
- **No AI can beat rules on this data** — the labels ARE the rules. Which is why the last eval printed:

```
Rule Based   ₹345,836  38 wrong  0.740
ML Only      ₹345,836  38 wrong  0.740
KTHMA        ₹345,836  38 wrong  0.740
```

- **KTHMA is byte-identical in outcome to both "Rule Based" and "ML Only".** This alone disqualifies it from winning Track 03.

---

## 2. Brutal judge score
---

## 3. Core differentiator (ONE idea)

Compared candidate directions on novelty, business value, AI-necessity, depth, demoability, Razorpay relevance, measurability.

**Winner: (D) Learning from recovery outcomes**, expressed as:

> **KTHMA = a recovery policy that LEARNS the value of each recovery move per customer/payment context from its own outcomes, then acts to maximize incremental ₹ recovered — and visibly re-trains every time it recovers.**

Why this over the others:

- **(A) diagnosis** and **(B) action selection** in pure form collapse to rules → weak.
- **(F) intelligent refusal** is the most resonant *story* but not the core engine; it becomes a **learned output** of the value model (recover ⇒ E[value] < cost), not a hardcoded `repeated_failure → nothing`.
- **(C) sequencing** and **(H) customer context** are Razorpay-native, defensible *expressions* of the learning loop; folded in as policy inputs, not separate features.
- **(G) autonomous agent** reuses existing policy-gate scaffolding, adds no intelligence.

The central, memorable claim:

> **A rules engine picks an action from a type; KTHMA learns how much money each move actually recovers for each kind of customer and re-tunes itself from every outcome.**

That sentence differentiates KTHMA in a way a judge instantly recognizes, and it now *requires* signal + learning + evaluation → AI genuinely necessary.

---

## 4. Redesigned product

**New concept: "Recovery is a learned value policy, not a type→action lookup."**

### Input (features only — no ground truth)
- Payment context: amount, method, failure reason, attempt count, retry history, last-success age.
- **Customer recovery profile** (latent, unobserved): each customer has a hidden quality ("retry-responsive", "link-responsive", "dead-card", "churn risk") that shapes outcomes. The agent must *infer* it from observable history. This is the learnable signal.
- **Position in sequence**: how many recovery attempts already received (first vs third nudge) — drives cost-of-annoyance.

### Reasoning (what AI must infer)
- The latent per-customer recovery type from a noisy history.
- Non-linear **interaction effects**: e.g. *UPI + bank-timeout + ≥5 prior successes* → retry wins; *card + authentication_failed + low history* → payment-link wins; *wallet + 3 failed attempts in 24h* → stop.
- **Uncertainty** (a probability on each action), not a single hardcoded P.

So the model predicts `E[₹ recovered | context, action]` for each candidate action — and its inverse, `harm` (annoyance/churn cost of a wrong nudge), so "do nothing" wins when expected value ≤ cost.

### Decision
argmax over actions of `(E[₹ recovered] − cost)`. `do_nothing` is a first-class action on the same axis, not a hardcoded exclusion.

### Policy gate (real tiers)
- **Low risk / high confidence, ≤ ₹X, action `payment_link`/`reminder`** → auto-execute.
- **`retry_payment`/`retry_subscription` (money-moving)** → operator approval (as now).
- **NEVER:** anything on a flagged/fraud history; anything above a ₹ cap; the LLM calling Razorpay directly.

### Execution (honest boundary)
- **REAL Test Mode:** `payment_link` (create link), `reminder` (link + `reminder_enable`). Poll/payment webhook for `paid`.
- **SIMULATED (labelled):** `retry_payment`, `retry_subscription` (Razorpay has no merchant-side retry/charge endpoint without an order/subscription object). Be explicit: "Real link, simulated retry."
- Respect the 30-link Test Mode cap: demo creates ≤3 real links.

### Verification
A payment is "recovered" only when the world (simulator) or a Razorpay `paid` event confirms settlement. No unverified claims.

### Learning
The agent trains a **contextual recovery-value model** on *development-set execution outcomes* (which (context, action) actually recovered ₹, at what harm). Deploys that policy to hold-out. Every recovered/failed outcome in the demo appends to a training set — the "learning loop" becomes a visible, working feature.
---

## 5. Making AI genuinely necessary

Today a judge says "couldn't this be if/else?" — because it literally is. Two changes erase that:

1. **Give the data real (noisy, non-linear, latent-context) signal.** Recoverability and best-action must depend on *combinations* of features and an unobserved per-customer recovery type. Then a rules engine is provably wrong on a meaningful fraction, linear ML is wrong on interaction cases, and only a model that captures interactions + latent type wins materially.
2. **Use learning to choose the action by value.** The decision comes out of a learned `E[₹|context, action]` model, not a lookup table. This is the provable, hold-out-measurable gap over Rule-Based.

Keep deterministic where deterministic is safer (detection-precursor, policy gate, execution, verification, safety). **LLM is optional** — not needed to win; if added, put it only at Diagnosis/Why (per ADR 0006), never in the value function or the policy gate.

---

## 6. Evaluation as the killer feature

Keep the leak-proof design. **Rework the output to a money-first scorecard:**

```
On the SAME 1,000 hold-out cases (seed 42):

METHOD          RECOVERABLE  ₹ RECOVERED  RECOVERY RATE  FALSE INTERVENTIONS  UNNECESSARY ₹
Always Retry     ₹X          ₹Y           z%             100                   ₹W
Rule Based       ₹X          ₹Y2          z2%            38                    ₹W2
ML Only          ₹X          ₹Y3          z3%            38                    ₹W3
KTHMA            ₹X          ₹Y4          z4%            23                    ₹W4

INCREMENTAL VS RULES:  +₹(Y4-Y2) recovered  ·  −(38-23) harmful interventions  ·  net value +₹N
```

Add to the metrics object: **per-action precision**, **incremental ₹ vs each baseline**, **estimated harm saved** (value of avoided false interventions), **intentionally-skipped cases** (granular, not one bucket). Show **"KTHMA improves with feedback"**: fit → score → log 300 outcomes → re-fit → score again → note the delta.

Reproducibility and no-leak stay untouched and become a shippable `evaluate.py` the judge can run.

---

## 7. Demo redesign (2-minute judge attention)

First screen = the money + the counterfactual, not a generic dashboard:

```
REVENUE AT RISK        ₹18.4L      (1,000 cases)
KTHMA RECOVERED        ₹7.8L
vs RULES               +₹2.2L      incremental
vs ALWAYS-RETRY        +₹5.1L
HARMFUL INTERVENTIONS  4%          (rules: 11%)
```

Then one drill-in: **case → context → Diagnosis → candidate actions w/ E[₹] → selected strategy → Policy → Execute (real link or labelled sim) → Verify → ₹ recovered → "what the rules engine would have done"** side-by-side. "Why" stays an evidence summary (no hidden chain-of-thought).

---

## 8. Killer demo scenario

**"The case a rules engine gets wrong, KTHMA gets right."**

Two customers, identical surface facts (repeated failed payment, ₹2,499) — but one has a **transient** issue (high recent success density, retry-responsive) and the other a **dead instrument** (long dead-streak, zero response to nudges). A rules engine treats both as `repeated_failure → do_nothing → ₹0` (or blindly retries and annoys).

KTHMA's learned value model separates them: it **retries the transient one and recovers ₹2,499, and correctly refuses the dead one** (saving the annoyance a rule would've caused). The screen shows the two side-by-side, the incremental ₹, and the avoided intervention.

Why it works: it demonstrates **learned intelligent refusal AND learned action selection** — AGENTS.md's "do not retry" made intelligent instead of hardcoded. Basic rules can't win it by construction.
---

## 9. KEEP / DELETE / CHANGE / ADD

### KEEP
- Typed dataclass contracts & seam design.
- Leak-proof 80/20 split, reproducible seed.
- Policy gate + labelled simulator + fail-closed Razorpay (safety instincts).
- Payment Links transport + paise/reference handling (verified docs).
- FastAPI + SQLite + the good dashboard bones.
- The 65 tests. The honest simulator grounding.

### DELETE
- **The "3 identical baselines" illusion.** Leave Always-Retry and Rule-Based; drop/replace the ML baseline until meaningfully different from rules (or keep it as the *reactive-ML strawman* you beat — it must genuinely learn, not share the rule action table).
- `detect` as a no-op reading `amount`.
- Hardcoded `best_action = rng.choice` and `recoverable = rng.random()<0.95` (replace with signal-bearing generation).
- The hardcoded decision if/elif (replace with the learned value policy). Keep a thin default for cold-start.

### CHANGE
- **Generator → procedural-but-signaled ground truth** (latent per-customer recovery type + nonlinear, noisy action/outcome dependence). Highest-leverage change.
- **Decision → learned `E[₹|context, action]` value model** with `do_nothing` on the same axis (learned refusal).
- **Diagnosis → multi-signal**, still explainable.
- **Probability → model uncertainty**, not a constant formula.
- **Policy gate → real tiers** (auto / approval / never + ₹ cap + fraud flags).
- **Evaluation → money-first scorecard** with per-action precision + incremental + harm + learning loop.
- **Dashboard → counterfactual-first** (KTHMA vs Rules up top), case drill-in with "what rules would do."
- **Demo → pinned counterfactual scenario** (transient vs dead instrument).
- **Add a real README** stating one thing: *why KTHMA beats a rules engine, with the eval as proof.*

### ADD (ranked)

| Change | Impact | Difficulty | Demo value | Differentiation |
|---|---|---|---|---|
| Signaled generator (latent recovery-type) | 10 | 3 | 7 | 10 |
| Learned value policy + learned refusal | 10 | 5 | 8 | 10 |
| Money-first eval + incremental & harm | 10 | 2 | 9 | 9 |
| Counterfactual demo scenario | 9 | 2 | 10 | 9 |
| Real tiered policy gate | 7 | 2 | 6 | 6 |
| README / judge narrative | 8 | 1 | 8 | 7 |
| Working learning-loop (re-fit from outcomes) | 8 | 4 | 7 | 8 |
| Razorpay verification (webhook/poll) on demo path | 6 | 3 | 5 | 5 |

### MVP (smallest set to stop being "basic")
1. **Signaled generator** with a latent per-customer recovery type → real, learnable, non-linear labels.
2. **Learned value policy** (sklearn/logistic w/ interaction features or LightGBM) choosing action by `E[₹]−cost`, including learned refusal.
3. **Money-first evaluation** with incremental vs Always-Retry and vs Rule-Based, on the untouched hold-out.
4. **Counterfactual demo scenario** + **README**.

### FINALIST VERSION
Add: working **learning loop** (outcomes → re-train → re-score delta), **real tiered policy gate** with ₹ cap + auto-execute tier, **Razorpay verification on the demo path** (real link + poll/`paid`), richer harm/cost accounting, **dashboard leading with the incremental-vs-rules number**.

### DO NOT BUILD
- Microservices / Kafka / Kubernetes / vector DBs.
- Multi-LLM agent frameworks passing prose.
- Fake "live" Razorpay claims. Fake recovered money.
- A second ML stack "for looks." Complicated integration surfaces.
- Anything not in the money-first story.

---

## 10. Top 3 things that most increase the chance of winning

1. **Fix the data** so recoverability/action depends on latent, non-linear, learnable context — without this nothing else works, and it's cheap.
2. **Make KTHMA provably beat Rule-Based and Always-Retry on the hold-out**, shown as **incremental ₹ recovered + avoided harmful interventions** on the first dashboard screen and in the README.
3. **Ship a killer counterfactual demo** (transient-retry vs dead-instrument-refusal) plus a **real README** so a judge can re-run the eval and reproduce the win in two minutes.