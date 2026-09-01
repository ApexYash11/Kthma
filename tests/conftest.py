"""pytest config: keep random-forest fits fast during the test suite.

fit_policy reads KTHMA_N_ESTIMATORS (default 200). Tests set a lower count so
the heavy signal/report/demo tests finish in seconds while keeping the
strong-differentiation assertions intact. Run full-strength with
KTHMA_N_ESTIMATORS=200 pytest tests/ -q if you want the exact prod model.
"""

import os

os.environ.setdefault("KTHMA_N_ESTIMATORS", "25")