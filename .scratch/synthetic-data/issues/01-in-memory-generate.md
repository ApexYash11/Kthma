# 01: In-memory generate

**What to build:** Calling `generate(seed, n, config)` returns a SplitDataset in memory. Same seed reproduces. n=100 is 80 development / 20 hold-out. n≥20 includes leakage types for scenarios A–D. Features contain no ground truth. Ground truth has recoverable, best_action, expected outcome, and amount, keyed by recovery-case ID.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `generate(seed, n, config)` is the only public seam
- [ ] Same seed + n + config yields identical IDs, amounts, leakage types, and labels
- [ ] n=100 → 80 development / 20 hold-out
- [ ] Development and hold-out recovery-case IDs do not overlap
- [ ] Feature records have no recoverable, best_action, expected_outcome, or intended scenario fields
- [ ] Ground truth records include recoverable, best_action, expected_outcome, and amount
- [ ] n≥20 includes payment failure, checkout abandonment, subscription failure, and repeated failure (do-nothing)
- [ ] No LLM, Razorpay, ML, or frontend
