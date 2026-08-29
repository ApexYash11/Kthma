"""Dashboard API: summary, cases, investigation, evaluation. Data from SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from kthma import load_features, load_ground_truth
from kthma.execution import GroundedSimulatorExecutor
from kthma.pipeline import run_case
from kthma.report import format_report, run_evaluation

app = FastAPI(title="KTHMA", version="0.1.0")
DB_PATH = "dataset.sqlite3"

BANNER = "DEMO MERCHANT · SYNTHETIC DATA"


def _banner_row() -> dict:
    return {"banner": BANNER}


def _executor():
    truth = load_ground_truth(DB_PATH, "development") + load_ground_truth(DB_PATH, "holdout")
    return GroundedSimulatorExecutor({g.recovery_case_id: g.recoverable for g in truth})


@app.get("/api/summary")
def summary() -> dict:
    features = load_features(DB_PATH, "development")
    truth = load_ground_truth(DB_PATH, "development")
    at_risk = sum(f.amount for f in features)
    recoverable = sum(g.amount for g in truth if g.recoverable)
    executor = _executor()
    recovered = 0
    for f in features:
        report = run_case(f, executor)
        if report.verification.outcome == "recovered":
            recovered += report.verification.recovered_amount
    return {
        **_banner_row(),
        "revenue_processed": 12_450_000,  # demo-merchant top line, synthetic
        "revenue_at_risk": at_risk,
        "recoverable": recoverable,
        "recovered": recovered,
        "recovery_rate": round(recovered / recoverable, 4) if recoverable else 0.0,
        "case_count": len(features),
    }


@app.get("/api/cases")
def cases() -> dict:
    features = load_features(DB_PATH, "development")
    truth = {g.recovery_case_id: g for g in load_ground_truth(DB_PATH, "development")}
    items = []
    for f in features:
        decision = run_case(f).decision
        items.append(
            {
                "recovery_case_id": f.recovery_case_id,
                "amount": f.amount,
                "type": f.leakage_type,
                "recommended_action": decision.action,
                "expected_recovery": decision.expected_recovery_value,
            }
        )
    return {**_banner_row(), "cases": items, "ground_truth_available_for_scoring_only": len(truth) > 0}


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str) -> dict:
    features = load_features(DB_PATH, "development") + load_features(DB_PATH, "holdout")
    match = next((f for f in features if f.recovery_case_id == case_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="recovery case not found")
    report = run_case(match, _executor())
    return {
        **_banner_row(),
        "case": asdict(report.detection) | {"amount": match.amount},
        "diagnosis": asdict(report.diagnosis),
        "decision": asdict(report.decision),
        "policy": asdict(report.policy),
        "timeline": [asdict(step) for step in report.timeline],
    }


@app.get("/api/evaluate")
def evaluate() -> dict:
    from kthma import generate

    dataset = generate(seed=42, n=500)
    report = run_evaluation(dataset)
    return {**_banner_row(), "report": {k: asdict(v) for k, v in report.methods.items()}, "table": format_report(report)}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return (
        "<!doctype html><html><head><title>KTHMA</title>"
        "<style>body{font-family:system-ui;background:#0b1220;color:#e6edf7;margin:0}"
        "header{background:#111a2e;padding:14px 24px;display:flex;justify-content:space-between}"
        ".banner{background:#7a2e2e;padding:4px 10px;border-radius:4px;font-size:12px}"
        "main{padding:24px;max-width:900px}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}"
        ".card{background:#151f36;padding:16px;border-radius:8px}.card h3{margin:0;font-size:12px;color:#8aa0c4}"
        ".card p{margin:6px 0 0;font-size:22px}table{width:100%;border-collapse:collapse;margin-top:20px}"
        "td,th{padding:8px;border-bottom:1px solid #22304e;text-align:left;font-size:13px}</style></head><body>"
        f"<header><strong>KTHMA</strong><span class='banner'>{BANNER}</span></header><main>"
        "<div id='summary' class='grid'></div><h3>Active recovery cases</h3>"
        "<table id='cases'></table><h3>Evaluation (hold-out)</h3><pre id='eval'></pre></main>"
        "<script>fetch('/api/summary').then(r=>r.json()).then(d=>{document.getElementById('summary').innerHTML="
        "['revenue_at_risk','recoverable','recovered','recovery_rate','case_count'].map(k=>"
        "`<div class='card'><h3>${k}</h3><p>${d[k]}</p></div>`).join('')});"
        "fetch('/api/cases').then(r=>r.json()).then(d=>{document.getElementById('cases').innerHTML="
        "'<tr><th>Case</th><th>Amount</th><th>Type</th><th>Action</th><th>Expected</th></tr>'+"
        "d.cases.slice(0,10).map(c=>`<tr><td>${c.recovery_case_id}</td><td>${c.amount}</td><td>${c.type}</td>"
        "<td>${c.recommended_action}</td><td>${c.expected_recovery}</td></tr>`).join('')});"
        "fetch('/api/evaluate').then(r=>r.json()).then(d=>{document.getElementById('eval').textContent=d.table});"
        "</script></body></html>"
    )
