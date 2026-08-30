"""Dashboard API: summary, cases, investigation, evaluation. Data from SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from kthma import load_features, load_ground_truth
from kthma.execution import GroundedSimulatorExecutor, HybridRazorpayExecutor, RazorpayPaymentLinkTransport
from kthma.models import RecoveryCaseFeatures
from kthma.pipeline import CaseReport, run_case
from kthma.report import format_report, run_evaluation

app = FastAPI(title="KTHMA", version="0.1.0")
DB_PATH = "dataset.sqlite3"

BANNER = "DEMO MERCHANT · SYNTHETIC DATA"

LEAKAGE_LABELS = {
    "payment_failure": "Payment failure",
    "checkout_abandonment": "Checkout abandonment",
    "subscription_failure": "Subscription failure",
    "repeated_failure": "Repeated failure (do nothing)",
}


def _banner_row() -> dict:
    return {"banner": BANNER}


def _all_features() -> tuple[RecoveryCaseFeatures, ...]:
    return load_features(DB_PATH, "development") + load_features(DB_PATH, "holdout")


def _all_truth():
    return load_ground_truth(DB_PATH, "development") + load_ground_truth(DB_PATH, "holdout")


def _executor():
    if os.environ.get("KTHMA_EXECUTOR") == "razorpay":
        transport = RazorpayPaymentLinkTransport(
            key_id=os.environ["RAZORPAY_KEY_ID"], key_secret=os.environ["RAZORPAY_KEY_SECRET"]
        )
        return HybridRazorpayExecutor(transport)
    return GroundedSimulatorExecutor(
        {g.recovery_case_id: (g.recoverable, g.best_action) for g in _all_truth()}
    )


def _report_for(case_id: str) -> CaseReport:
    match = next((f for f in _all_features() if f.recovery_case_id == case_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="recovery case not found")
    return run_case(match, _executor())


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
    items = []
    for f in features:
        report = run_case(f, _executor())
        items.append(
            {
                "recovery_case_id": f.recovery_case_id,
                "amount": f.amount,
                "type": f.leakage_type,
                "type_label": LEAKAGE_LABELS.get(f.leakage_type, f.leakage_type),
                "root_cause": report.diagnosis.root_cause,
                "probability": report.decision.probability_of_success,
                "recommended_action": report.decision.action,
                "expected_recovery": report.decision.expected_recovery_value,
                "outcome": report.verification.outcome,
            }
        )
    return {**_banner_row(), "cases": items}


@app.get("/api/breakdown")
def breakdown() -> dict:
    features = load_features(DB_PATH, "development")
    result: dict[str, dict] = {}
    for key in LEAKAGE_LABELS:
        subset = [f for f in features if f.leakage_type == key]
        result[key] = {
            "label": LEAKAGE_LABELS[key],
            "cases": len(subset),
            "amount_at_risk": sum(f.amount for f in subset),
        }
    return {**_banner_row(), "breakdown": result}


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str) -> dict:
    report = _report_for(case_id)
    return {
        **_banner_row(),
        "diagnosis": asdict(report.diagnosis),
        "decision": asdict(report.decision),
        "policy": asdict(report.policy),
        "timeline": [asdict(step) for step in report.timeline],
        "verification": asdict(report.verification),
    }


@app.post("/api/cases/{case_id}/approve")
def approve_case(case_id: str) -> dict:
    """Operator approval: run policy-checked execution and return the verified result."""
    report = _report_for(case_id)
    if report.decision.action == "do_nothing":
        raise HTTPException(status_code=409, detail="case is a do-nothing; nothing to approve")
    return {
        **_banner_row(),
        "executed": report.verification.outcome == "recovered",
        "execution": asdict(report.execution) if report.execution else None,
        "verification": asdict(report.verification),
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
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>KTHMA — Revenue Recovery</title>
<style>
:root{--bg:#0b1220;--panel:#131c30;--panel2:#1a2742;--line:#22304e;--txt:#e6edf7;--mut:#8aa0c4;--acc:#4f8cff;--ok:#2ecc8f;--warn:#f0b429;--bad:#e5484d}
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--txt)}
header{display:flex;align-items:center;justify-content:space-between;padding:14px 28px;background:#0e1728;border-bottom:1px solid var(--line)}
header h1{margin:0;font-size:18px;letter-spacing:2px}.banner{background:#6b2f2f;color:#ffd9d9;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:600}
main{padding:24px 28px;max-width:1100px;margin:0 auto}
h2{font-size:14px;color:var(--mut);text-transform:uppercase;letter-spacing:1px;margin:26px 0 10px}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.card h3{margin:0;font-size:11px;color:var(--mut);text-transform:uppercase}
.card p{margin:8px 0 0;font-size:22px;font-weight:700}.ok{color:var(--ok)}
.brk{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.brk .card p{font-size:16px}.brk .small{font-size:12px;color:var(--mut);font-weight:400;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th{font-size:11px;text-transform:uppercase;color:var(--mut);text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
td{padding:10px 12px;border-bottom:1px solid var(--line);font-size:13px}
tr.click{cursor:pointer}tr.click:hover{background:var(--panel2)}
.tag{padding:2px 8px;border-radius:10px;font-size:11px}.tag.recovered{background:#123c2e;color:var(--ok)}.tag.no_action_taken{background:#22304e;color:var(--mut)}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:8px 16px;font-weight:600;cursor:pointer}
button:disabled{background:var(--line);color:var(--mut);cursor:default}
#panel{display:none;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px;margin-top:16px}
#panel h3{margin:0 0 4px}.step{display:flex;gap:10px;padding:7px 0;border-bottom:1px dashed var(--line);font-size:13px}
.step b{color:var(--acc);min-width:86px}.ev{font-size:12px;color:var(--mut);margin:8px 0;line-height:1.6}
pre{background:#0d1526;border:1px solid var(--line);border-radius:8px;padding:14px;font-size:12px;overflow-x:auto}
.dv{display:flex;gap:18px;margin-top:10px;flex-wrap:wrap}.dv div{font-size:13px}.dv b{color:var(--acc)}
</style></head><body>
<header><h1>KTHMA</h1><span class="banner">DEMO MERCHANT · SYNTHETIC DATA</span></header>
<main>
<div class="cards" id="cards"></div>
<h2>Leakage breakdown</h2><div class="brk" id="brk"></div>
<h2>Active recovery cases</h2>
<table><thead><tr><th>Case</th><th>Amount</th><th>Type</th><th>Root cause</th><th>P(recovery)</th><th>Recommended</th><th>Expected</th><th>Status</th></tr></thead>
<tbody id="cases"></tbody></table>
<div id="panel">
  <h3 id="p-title"></h3><div class="ev" id="p-evidence"></div>
  <div class="dv" id="p-decision"></div>
  <div id="p-steps" style="margin-top:12px"></div>
  <div style="margin-top:14px"><button id="approve">Approve &amp; Execute</button> <span id="p-msg" style="font-size:13px;color:var(--mut)"></span></div>
</div>
<h2>Evaluation (hold-out, seed 42)</h2><pre id="eval">loading…</pre>
</main>
<script>
const fmt = n => '\\u20B9' + Number(n).toLocaleString('en-IN');
// PART2
fetch('/api/summary').then(r=>r.json()).then(d=>{
  const items=[['Revenue at risk',d.revenue_at_risk],['Recoverable',d.recoverable],['Recovered',d.recovered,'ok'],['Recovery rate',(100*d.recovery_rate).toFixed(1)+'%','ok'],['Recovery cases',d.case_count]];
  document.getElementById('cards').innerHTML=items.map(([k,v,c])=>`<div class="card"><h3>${k}</h3><p class="${c||''}">${(typeof v==='number'&&k!=='Recovery cases'&&k!=='Recovery rate')?fmt(v):v}</p></div>`).join('');
});
fetch('/api/breakdown').then(r=>r.json()).then(d=>{
  document.getElementById('brk').innerHTML=Object.values(d.breakdown).map(e=>`<div class="card"><h3>${e.label}</h3><p>${fmt(e.amount_at_risk)}</p><p class="small">${e.cases} cases</p></div>`).join('');
});
let selected=null;
fetch('/api/cases').then(r=>r.json()).then(d=>{
  document.getElementById('cases').innerHTML=d.cases.map(c=>`<tr class="click" onclick="investigate('${c.recovery_case_id}')">
  <td>${c.recovery_case_id}</td><td>${fmt(c.amount)}</td><td>${c.type_label}</td><td>${c.root_cause}</td>
  <td>${Math.round(c.probability*100)}%</td><td>${c.recommended_action}</td><td>${fmt(c.expected_recovery)}</td>
  <td><span class="tag ${c.outcome}">${c.outcome}</span></td></tr>`).join('');
});
async function investigate(id){
  selected=id;
  const d=await (await fetch('/api/cases/'+id)).json();
  document.getElementById('panel').style.display='block';
  document.getElementById('p-title').textContent='Investigation · '+id;
  document.getElementById('p-evidence').textContent='Evidence: '+d.diagnosis.evidence.join(' · ');
  document.getElementById('p-decision').innerHTML=
    `<div><b>Action</b> ${d.decision.action}</div><div><b>Amount</b> ${fmt(d.decision.amount)}</div>`+
    `<div><b>P(success)</b> ${Math.round(d.decision.probability_of_success*100)}%</div>`+
    `<div><b>Expected recovery</b> ${fmt(d.decision.expected_recovery_value)}</div>`+
    `<div><b>Why</b> ${d.decision.rationale}</div><div><b>Policy</b> ${d.policy.risk_level} risk · approval ${d.policy.requires_approval?'required':'not required'}</div>`;
  document.getElementById('p-steps').innerHTML=d.timeline.map(s=>`<div class="step"><b>${s.stage}</b><span>${s.detail}</span></div>`).join('');
  const btn=document.getElementById('approve');
  btn.disabled=d.verification.outcome==='recovered'||d.decision.action==='do_nothing';
  document.getElementById('p-msg').textContent=d.verification.outcome==='recovered'?'Already executed and verified.':'';
}
document.getElementById('approve').onclick=async()=>{
  if(!selected)return;
  const r=await fetch('/api/cases/'+selected+'/approve',{method:'POST'});
  const d=await r.json();
  const msg=document.getElementById('p-msg');
  if(r.ok&&d.executed){msg.textContent='\\u2713 Executed via '+d.execution.adapter+' \\u2014 verified '+fmt(d.verification.recovered_amount)+' recovered';
    document.getElementById('approve').disabled=true;investigate(selected);setTimeout(()=>location.reload(),1200);}
  else{msg.textContent='\\u2717 '+(d.detail||(d.execution&&d.execution.detail)||'execution failed');}
};
fetch('/api/evaluate').then(r=>r.json()).then(d=>{document.getElementById('eval').textContent=d.table});
</script></body></html>"""
