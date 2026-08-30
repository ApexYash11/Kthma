# Razorpay Test Mode — execute vs simulate research

**Status:** verified against official docs (razorpay.com/docs, LLM markdown mirrors at `/docs/build/llm-docs/...`, fetched 2026-08-30).

## Verified API facts

### Create Standard Payment Link

- `POST https://api.razorpay.com/v1/payment_links/`
- Auth: HTTP Basic, `-u KEY_ID:KEY_SECRET` (Test Mode keys are `rzp_test_...`).
- Body fields (JSON):
  - `amount`: integer **in paise** (subunits). Rs2,499 -> `249900`. Whole numbers only; minimum 100 for INR.
  - `currency`: `"INR"`.
  - `customer`: `{ name, email, contact }` — name non-empty; contact 8-14 chars incl. country code; email valid format.
  - `notify`: `{ "sms": true, "email": true }` — Razorpay sends the link; we do NOT own a notifier (ADR 0004 satisfied).
  - `reminder_enable`: boolean — built-in SMS reminders; our "audit-only reminder" maps to this, not a custom provider.
  - `reference_id`: <=40 chars — we store the KTHMA recovery-case ID here.
  - `expire_by`: UNIX epoch seconds integer.
  - `accept_partial` / `first_min_partial_amount`: only if partial allowed (we set `accept_partial: false`).
  - `notes`: free-form map (we store recovery_case_id + risk level).
  - `callback_url` + `callback_method` (`get` only) for post-payment redirect.
- Response: `id` (`plink_...`), `short_url`, `status`.
- Errors: 400 with field-specific messages (doc error table).

### Payment link lifecycle (Standard)

`created` -> `partially_paid` -> `paid` | `cancelled` | `expired`

- Cancel only allowed in `issued`/`created` state; never after `partially_paid`/`paid`.
- Verification: poll fetch API or webhook for `paid`; verify `razorpay_signature` on callbacks (HMAC SHA256).

### Test Mode constraints (design-relevant)

- **Test Mode cap: 30 payment links per business.** Batch evaluation must NOT create real links; only the operator-approved demo path does. KTHMA demo creates <=3 links — safe.
- Test Mode never moves real money.
- Test UPI/card ids for simulating success/failure to be confirmed at key-onboarding time (page fetch not completed; non-blocking).

## Execute vs simulate split (ADR 0003)

| Recovery action | Path | Why |
|---|---|---|
| `payment_link` | **Real Test Mode API** (approved cases only) | Payment Links API is the exact product for this. |
| `reminder` | Real link with `reminder_enable: true` | Built-in; no custom notifier. |
| `retry_payment` | **Simulator** | Razorpay has no "retry my charge" endpoint; a retry is a merchant-side re-charge. Labelling it SIMULATOR is honest. |
| `retry_subscription` | **Simulator** | Subscriptions API needs an existing Razorpay subscription object our synthetic data lacks. Revisit with a real demo subscription. |
| `do_nothing`, `escalate` | No execution | By definition. |

Executor selection: `KTHMA_EXECUTOR=simulator|razorpay` (default `simulator`, fail-closed without `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET`).

## Before first live Test Mode call

1. Set `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` (Test Mode).
2. Run executor tests with a fake transport (in `tests/test_razorpay.py`).
3. Create one real Rs1 link, pay it with a test instrument, confirm `paid` via fetch, then enable in the demo.
