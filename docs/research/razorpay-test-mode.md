# Razorpay Test Mode — execute vs simulate research

**Status:** incomplete — blocked on network access to razorpay.com docs and on Test Mode keys.

## Verified decisions (ADRs, no API facts needed)

- Execution default is the labelled `SimulatorExecutor` until Test Mode keys exist (ADR 0003).
- `RazorpayExecutor` fails closed: constructing/using it without `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` raises; it never pretends a real call happened (ADR 0005 fail-closed principle applied to payments).
- No custom email/SMS notifier; reminders are audit-only (ADR 0004).
- The LLM never calls payment APIs; Execution is a controlled tool layer (AGENTS.md policy).

## Must verify against official docs before wiring the real client

Do **not** treat the following as facts. Verify each against razorpay.com/docs before implementing:

1. Payment Links create endpoint path and required body fields (amount in paise vs rupees, currency, customer contact fields).
2. Auth scheme for API keys (expected: HTTP Basic with `key_id:key_secret` — unverified here).
3. How to poll or webhook payment-link status (`paid` event) for Verification.
4. Test Mode behaviour: that test keys never move real money, and any test UPI/card ids usable in the demo.
5. Subscriptions/retry endpoints if we execute `retry_subscription` for real.

## Consequence for Phase 6 demo

Demo runs through `SimulatorExecutor`, labelled `SIMULATOR` on the audit timeline and dashboard. When keys exist: set env vars, flip the executor, re-run the same pipeline tests with a fake transport before any live Test Mode call.
