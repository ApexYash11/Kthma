# KTHMA

AI revenue recovery for merchants. Razorpay Buildathon Track 03. This glossary is the shared language for chat, tickets, tests, and code.

## Product

**KTHMA**:
This product. Not a generic chatbot.
_Avoid_: RevPilot, the app, the AI, copilot

**Demo merchant**:
The labelled synthetic merchant shown in the dashboard and demo. KTHMA operates on this one merchant only.
_Avoid_: Live merchant, production merchant, multi-merchant ops

**Operator**:
The merchant ops person who investigates recovery cases.
_Avoid_: End customer, Razorpay admin, founder-as-primary-persona

**Synthetic data**:
Generated transactions with known ground truth, always labelled as synthetic.
_Avoid_: Production data, real merchant data

## Pipeline

**Leakage**:
Revenue that failed, was abandoned, or otherwise did not complete.
_Avoid_: Lost sales, drop-off (as a catch-all)

**Revenue at risk**:
Amount of leakage currently in scope. Headline detection number.
_Avoid_: Opportunity size

**Recoverable revenue**:
Subset of revenue at risk where a recovery action is justified.
_Avoid_: Treating all leakage as recoverable

**Recovered revenue**:
Amount actually recovered after execution and verification. Headline metric: ₹ recovered.
_Avoid_: Claiming recovery before verification

**Recovery rate**:
Recovered divided by recoverable. Denominator must match in code and UI.
_Avoid_: Retry success percent

**Recovery case**:
One leakage instance under investigation.
_Avoid_: Ticket, lead, alert

**Investigation**:
The evidence timeline for one recovery case.
_Avoid_: Chat transcript, hidden chain-of-thought

**Why**:
A projection of the Decision: concise evidence and decision factors. No hidden chain-of-thought.
_Avoid_: Model scratchpad, chatbot reply

## Decisions

**Recovery action**:
retry payment, payment link, reminder, alternate method, retry subscription, escalate, or do nothing.
_Avoid_: Nudge, campaign

**Expected recovery value**:
`amount × probability_of_success`. The decision score.
_Avoid_: Ranking by probability alone

**Policy gate**:
Safety check before execution. Low = auto. Medium = approval. High or money-moving = explicit approval.
_Avoid_: Letting the LLM call payment APIs directly

**Do nothing**:
A valid action when retry would be wasteful or harmful.
_Avoid_: Always retry

## Leakage types

**Payment failure**:
An attempted payment failed. Scenario A.

**Checkout abandonment**:
The customer entered the payment flow and left. Scenario B.

**Subscription failure**:
A recurring charge failed. Scenario C.

## Evaluation

**Ground truth**:
Hidden labels for recoverable?, best action, and expected outcome. Stored off the model-visible feature set.
_Avoid_: Feeding labels into Detection or Decision

**Hold-out**:
1000 labelled records the system must not train or tune on.
_Avoid_: Peeking then reporting those numbers as generalization

**Baseline**:
Always-retry, rule-based, and ML-only. KTHMA is compared against these on the same test data.
_Avoid_: Invented dashboard figures

## Architecture

**Module**:
A pipeline stage with a typed interface: Detection, Diagnosis, Decision, Policy, Execution, Verification, Evaluation.
_Avoid_: Agent as a chatty LLM that only passes text

**Judgment stage**:
Diagnosis, Decision, or Why. The only stages allowed to call an LLM.
_Avoid_: Prompting Detection, Policy, Execution, Verification, or Evaluation

**Seam**:
The public contract you test through.
_Avoid_: Testing private prompts or internals

**Simulator**:
A clearly labelled stand-in for a recovery action that is not executed through Razorpay Test Mode. This is the Execution path until Test Mode keys exist.
_Avoid_: Fake API calls presented as real, silent no-op

**Audit-only reminder**:
A reminder recovery action recorded on the recovery case and investigation timeline, with no custom email or SMS provider.
_Avoid_: Twilio, SendGrid, or any notifier we own
