"""Dashboard API tests against a generated SQLite file."""

import pytest
from fastapi.testclient import TestClient

from kthma import generate, save_split
from kthma.execution import GroundedSimulatorExecutor
from kthma import api


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dataset.sqlite3")
    save_split(generate(seed=42, n=100), db_path)
    monkeypatch.setattr(api, "DB_PATH", db_path)
    return TestClient(api.app)


@pytest.fixture()
def executor():
    truth = api._all_truth()
    return GroundedSimulatorExecutor(
        {g.recovery_case_id: (g.recoverable, g.best_action) for g in truth}
    )


def test_summary_reports_banner_and_headline_metrics(client):
    data = client.get("/api/summary").json()
    assert data["banner"] == "DEMO MERCHANT · SYNTHETIC DATA"
    assert data["revenue_at_risk"] > 0
    # On a fresh DB with no approvals, recovered starts at 0 (not simulated).
    assert data["recovered"] == 0
    assert 0 <= data["recovery_rate"] <= 1
    # No fake revenue_processed metric.
    assert "revenue_processed" not in data


def test_cases_list_never_exposes_ground_truth_actions(client):
    data = client.get("/api/cases").json()
    for case in data["cases"]:
        assert "recoverable" not in case
        assert "best_action" not in case
        assert "expected_outcome" not in case


def test_case_detail_returns_investigation_timeline(client):
    cases = client.get("/api/cases").json()["cases"]
    case_id = cases[0]["recovery_case_id"]
    detail = client.get(f"/api/cases/{case_id}").json()
    stages = [step["stage"] for step in detail["timeline"]]
    # GET shows planned state: no ACT (execution happens only on approve).
    assert "DETECT" in stages
    assert "DIAGNOSE" in stages
    assert "DECIDE" in stages
    assert "POLICY" in stages
    assert "VERIFY" in stages
    assert detail["decision"]["rationale"]


def test_unknown_case_returns_404(client):
    assert client.get("/api/cases/rc_nope").status_code == 404


def test_evaluate_endpoint_returns_all_methods(client):
    data = client.get("/api/evaluate").json()
    assert set(data["report"]) == {"Always Retry", "Rule Based", "ML Only", "KTHMA"}


def test_approve_endpoint_executes_and_returns_updated_timeline(client):
    cases = client.get("/api/cases").json()["cases"]
    abandon = next(c for c in cases if c["type"] == "checkout_abandonment")
    detail = client.post(f"/api/cases/{abandon['recovery_case_id']}/approve").json()
    assert detail["executed"] is True
    assert detail["verification"]["outcome"] == "recovered"
    stages = [s["stage"] for s in detail["timeline"]]
    assert stages == ["DETECT", "DIAGNOSE", "DECIDE", "POLICY", "ACT", "VERIFY"]


def test_breakdown_endpoint_reports_leakage_by_type(client):
    data = client.get("/api/breakdown").json()
    assert set(data["breakdown"]) == {
        "payment_failure",
        "checkout_abandonment",
        "subscription_failure",
        "repeated_failure",
    }
    for entry in data["breakdown"].values():
        assert entry["cases"] >= 0
        assert entry["amount_at_risk"] >= 0


def test_journey_endpoint_has_funnel_and_headline_sources(client):
    data = client.get("/api/journey").json()
    stages = [s["stage"] for s in data["funnel"]]
    assert stages[0] == "Detected (revenue at risk)"
    # Funnel ends with executed, verified recovered, skipped (order may vary).
    assert "Verified recovered" in stages
    assert "Skipped (do nothing)" in stages
    assert data["headline_sources"][0]["metric"] == "Revenue at Risk"
    assert "ground truth" in data["headline_sources"][1]["how"]


def test_dashboard_html_carries_banner(client):
    html = client.get("/").text
    assert "DEMO MERCHANT · SYNTHETIC DATA" in html


def test_dashboard_html_leads_with_counterfactual_hero(client):
    html = client.get("/").text
    assert "Why KTHMA beats a rules engine" in html
    assert "cf-row" in html


def test_counterfactual_endpoint_reports_incremental_vs_rules(client):
    data = client.get("/api/counterfactual").json()
    assert data["kthma_recovered"] >= 0
    assert data["incremental_vs_rules"] > 0  # KTHMA makes more money than rules
    assert data["incremental_vs_always_retry"] > 0
    assert data["wrong_actions"]["kthma"] < data["wrong_actions"]["always_retry"]


def test_razorpay_approve_only_recovers_paid_link(monkeypatch, tmp_path):
    """On the real Razorpay path a link counts as recovered only after `paid`."""
    from kthma import api
    from kthma.execution import HybridRazorpayExecutor

    class FakeTransport:
        def __init__(self, status):
            self.status = status

        def request(self, method, path, payload=None):
            return {"id": "plink_1", "short_url": "https://rzp.io/i/x", "status": self.status}

    db = str(tmp_path / "d.sqlite3")
    save_split(generate(seed=11, n=60), db)
    monkeypatch.setattr(api, "DB_PATH", db)
    client = TestClient(api.app)

    # Pick a case where the policy recommends a money-moving action (pending_approval).
    pending = [
        c
        for c in client.get("/api/cases").json()["cases"]
        if c["outcome"] == "pending_approval"
    ]
    assert len(pending) >= 2, "need at least 2 pending_approval cases for this test"
    case_id = pending[0]["recovery_case_id"]

    # unpaid link -> approve must NOT claim recovery
    monkeypatch.setattr(api, "_executor", lambda: HybridRazorpayExecutor(FakeTransport("created")))
    bad = client.post(f"/api/cases/{case_id}/approve").json()
    assert bad["verified"]["paid"] is False
    assert bad["verification"]["outcome"] == "failed"

    # paid link -> approve claims recovery, verified paid True
    case_id2 = pending[1]["recovery_case_id"]
    monkeypatch.setattr(api, "_executor", lambda: HybridRazorpayExecutor(FakeTransport("paid")))
    good = client.post(f"/api/cases/{case_id2}/approve").json()
    assert good["verified"]["paid"] is True
    assert good["verification"]["outcome"] == "recovered"


def test_get_endpoints_never_execute(tmp_path, monkeypatch):
    """GET /api/cases, /api/summary, /api/journey must never call the executor.

    A counting fake executor detects any execute() call."""
    from kthma import api

    class CountingExecutor:
        def __init__(self):
            self.calls = 0

        def execute(self, request):
            self.calls += 1
            from kthma.execution import ExecutionResult
            return ExecutionResult(True, "SIMULATOR", "counted")

    counting = CountingExecutor()
    monkeypatch.setattr(api, "_executor", lambda: counting)

    db = str(tmp_path / "dataset.sqlite3")
    save_split(generate(seed=42, n=100), db)
    monkeypatch.setattr(api, "DB_PATH", db)
    from fastapi.testclient import TestClient
    client = TestClient(api.app)

    # GET endpoints that must not execute
    client.get("/api/summary")
    client.get("/api/cases")
    client.get("/api/journey")
    cases = client.get("/api/cases").json()["cases"]
    client.get(f"/api/cases/{cases[0]['recovery_case_id']}")

    assert counting.calls == 0, f"GET endpoints called executor {counting.calls} times"


def test_approve_twice_is_idempotent(tmp_path, monkeypatch):
    """Approving the same case twice must not execute twice.

    The second approve returns the stored result (already_approved=True)
    without re-running the action."""
    from kthma import api
    from kthma.execution import ExecutionResult

    class CountingSimulator:
        def __init__(self):
            self.calls = 0

        def execute(self, request):
            self.calls += 1
            return ExecutionResult(True, "SIMULATOR", "simulated execution succeeded")

    counting = CountingSimulator()
    monkeypatch.setattr(api, "_executor", lambda: counting)

    db = str(tmp_path / "dataset.sqlite3")
    save_split(generate(seed=42, n=100), db)
    monkeypatch.setattr(api, "DB_PATH", db)
    from fastapi.testclient import TestClient
    client = TestClient(api.app)

    abandon = next(
        c
        for c in client.get("/api/cases").json()["cases"]
        if c["type"] == "checkout_abandonment"
    )
    case_id = abandon["recovery_case_id"]

    # First approve: executes
    first = client.post(f"/api/cases/{case_id}/approve").json()
    assert first["executed"] is True
    assert first["already_approved"] is False

    # Second approve: returns stored result, does NOT execute again
    second = client.post(f"/api/cases/{case_id}/approve").json()
    assert second["already_approved"] is True
    assert counting.calls == 1, f"Executor called {counting.calls} times, expected 1"
