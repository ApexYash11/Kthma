"""Dashboard API tests against a generated SQLite file."""

import pytest
from fastapi.testclient import TestClient

from kthma import generate, save_split
from kthma import api


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dataset.sqlite3")
    save_split(generate(seed=42, n=100), db_path)
    monkeypatch.setattr(api, "DB_PATH", db_path)
    return TestClient(api.app)


def test_summary_reports_banner_and_headline_metrics(client):
    data = client.get("/api/summary").json()
    assert data["banner"] == "DEMO MERCHANT · SYNTHETIC DATA"
    assert data["revenue_at_risk"] > 0
    assert data["recovered"] > 0
    assert 0 <= data["recovery_rate"] <= 1


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
    assert stages == ["DETECT", "DIAGNOSE", "DECIDE", "POLICY", "ACT", "VERIFY"]
    assert detail["decision"]["rationale"]


def test_unknown_case_returns_404(client):
    assert client.get("/api/cases/rc_nope").status_code == 404


def test_evaluate_endpoint_returns_all_methods(client):
    data = client.get("/api/evaluate").json()
    assert set(data["report"]) == {"Always Retry", "Rule Based", "ML Only", "KTHMA"}


def test_dashboard_html_carries_banner(client):
    html = client.get("/").text
    assert "DEMO MERCHANT · SYNTHETIC DATA" in html
