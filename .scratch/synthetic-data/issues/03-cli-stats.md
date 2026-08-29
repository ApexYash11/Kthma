# 03: CLI + stats

**What to build:** `--rows` and `--seed` write the SQLite file and print counts, rates, ID overlap (zero), and missing-type flags.

**Blocked by:** 02 SQLite persist and reload

**Status:** ready-for-agent

- [x] `--rows` and `--seed` generate and persist
- [x] Stats print development/hold-out counts and leakage-type counts
- [x] Stats report zero ID overlap
- [x] Stats flag missing leakage types when n is below the documented minimum
