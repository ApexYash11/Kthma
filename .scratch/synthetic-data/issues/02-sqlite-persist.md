# 02: SQLite persist and reload

**What to build:** A SplitDataset can be written to SQLite and read back. A Detection-style read returns features only. Hold-out ground truth stays in its own store and is not mixed into features.

**Blocked by:** 01 In-memory generate

**Status:** ready-for-agent

- [ ] Features and ground truth persist in separate stores sharing recovery-case ID
- [ ] Reloading features does not expose recoverable, best_action, expected_outcome, or intended scenario
- [ ] Hold-out ground truth is not returned by a features-only read
- [ ] Round-trip preserves IDs, amounts, leakage types, and labels
