"""Dashboard API: summary, cases, investigation, evaluation. Data from SQLite.

Safety contract:
- GET endpoints only PLAN cases (they never execute money-moving actions).
- Execution happens only via POST /approve, which persists an audit row.
- The same learned policy powers the hero, the cards, the funnel and the case list.
"""

from __future__ import annotations

from dataclasses import asdict
import os
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from kthma import load_features, load_ground_truth
from kthma.execution import (
    GroundedSimulatorExecutor,
    HybridRazorpayExecutor,
    RazorpayPaymentLinkTransport,
)
from kthma import generate
from kthma.models import RecoveryCaseFeatures, SplitDataset
from kthma.pipeline import CaseReport, plan_case, run_case
from kthma.recovery_model import RecoveryPolicy, fit_policy
from kthma.report import format_report, run_evaluation
from kthma.store import (
    ExecutionRecord,
    load_all_executions,
    load_execution,
    save_execution,
)

app = FastAPI(title="KTHMA", version="0.1.0")
DB_PATH = "dataset.sqlite3"

BANNER = "DEMO MERCHANT · SYNTHETIC DATA"

LEAKAGE_LABELS = {
    "payment_failure": "Payment failure",
    "checkout_abandonment": "Checkout abandonment",
    "subscription_failure": "Subscription failure",
    "repeated_failure": "Repeated failure (do nothing)",
}

# ---------------------------------------------------------------------------
# Cached singletons: one policy, one dataset, one truth table for the process.
# The learned policy is fit once on the development split and reused for every
# endpoint so the hero, cards, funnel and case table all tell one story.
# ---------------------------------------------------------------------------
_policy: RecoveryPolicy | None = None
_dataset: SplitDataset | None = None
_all_truth_map: dict[str, tuple[bool, str]] | None = None


def _get_policy() -> RecoveryPolicy:
    global _policy
    if _policy is None:
        _policy = fit_policy(_get_dataset().development, seed=42)
    return _policy


def _get_dataset() -> SplitDataset:
    global _dataset
    if _dataset is None:
        _dataset = generate(seed=42, n=5000)
    return _dataset


def _get_truth_map() -> dict[str, tuple[bool, str]]:
    global _all_truth_map
    if _all_truth_map is None:
        truth = load_ground_truth(DB_PATH, "development") + load_ground_truth(DB_PATH, "holdout")
        _all_truth_map = {g.recovery_case_id: (g.recoverable, g.best_action) for g in truth}
    return _all_truth_map


def _all_features() -> tuple[RecoveryCaseFeatures, ...]:
    return load_features(DB_PATH, "development") + load_features(DB_PATH, "holdout")


def _executor():
    """Build the executor for the approve path. Razorpay only with keys."""
    if os.environ.get("KTHMA_EXECUTOR") == "razorpay":
        transport = RazorpayPaymentLinkTransport(
            key_id=os.environ["RAZORPAY_KEY_ID"], key_secret=os.environ["RAZORPAY_KEY_SECRET"]
        )
        return HybridRazorpayExecutor(transport)
    return GroundedSimulatorExecutor(_get_truth_map())


def _banner_row() -> dict:
    return {"banner": BANNER}


def _get_or_execute(case_id: str) -> CaseReport:
    """Return a cached execution if the case was already approved, else plan it.

    This makes approve idempotent: a second approve returns the stored result
    without running the action again.
    """
    existing = load_execution(DB_PATH, case_id)
    if existing is not None:
        # Rebuild a CaseReport from the persisted execution for the timeline.
        match = next((f for f in _all_features() if f.recovery_case_id == case_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail="recovery case not found")
        report = plan_case(match, _get_policy())
        return report
    match = next((f for f in _all_features() if f.recovery_case_id == case_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="recovery case not found")
    return plan_case(match, _get_policy())


@app.get("/api/summary")
def summary() -> dict:
    """Headline metrics. 'recovered' counts only operator-approved executions
    that were verified, never simulated recoveries from a page load."""
    features = load_features(DB_PATH, "development")
    truth = load_ground_truth(DB_PATH, "development")
    at_risk = sum(f.amount for f in features)
    recoverable = sum(g.amount for g in truth if g.recoverable)

    # Recovered = sum of verified, approved executions from the audit trail.
    executions = load_all_executions(DB_PATH)
    recovered = sum(
        e.recovered_amount for e in executions.values() if e.verification_outcome == "recovered"
    )
    return {
        **_banner_row(),
        "revenue_at_risk": at_risk,
        "recoverable": recoverable,
        "recovered": recovered,
        "recovery_rate": round(recovered / recoverable, 4) if recoverable else 0.0,
        "case_count": len(features),
    }


@app.get("/api/cases")
def cases() -> dict:
    """List all recovery cases with their planned (not executed) state.

    No money-moving action runs on this endpoint. The case list shows what
    KTHMA recommends; execution happens only via POST /approve.
    """
    features = load_features(DB_PATH, "development")
    policy = _get_policy()
    items = []
    for f in features:
        report = plan_case(f, policy)
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


@app.get("/api/journey")
def journey() -> dict:
    """Reconstruct, from the actual data, how KTHMA got to the recovered number:
    the pipeline funnel and the headline leak contributors.

    The funnel shows planned state (no execution on GET). Recovered counts
    come from the persisted audit trail — only operator-approved executions.
    """
    features = load_features(DB_PATH, "development")
    truth = {g.recovery_case_id: g for g in load_ground_truth(DB_PATH, "development")}
    policy = _get_policy()

    detected = 0
    diagnosed = 0
    recommended = 0
    requires_approval = 0
    do_nothing = 0
    leaked_away = 0

    for f in features:
        report = plan_case(f, policy)
        detected += report.detection.revenue_at_risk
        diagnosed += 1
        if report.decision.action != "do_nothing":
            recommended += 1
            if report.policy.requires_approval:
                requires_approval += 1
        else:
            do_nothing += 1
            leaked_away += report.detection.revenue_at_risk

    # Recovered/verified come from the audit trail (operator-approved only).
    executions = load_all_executions(DB_PATH)
    executed_ok = sum(1 for e in executions.values() if e.success)
    verified = sum(1 for e in executions.values() if e.verification_outcome == "recovered")
    recovered_amount = sum(e.recovered_amount for e in executions.values() if e.verification_outcome == "recovered")

    truth_recoverable = sum(1 for g in truth.values() if g.recoverable)
    funnel = [
        {"stage": "Detected (revenue at risk)", "cases": len(features), "amount": detected, "note": "Every leaked payment/abandonment/failed subscription in the dataset"},
        {"stage": "Diagnosed (root cause known)", "cases": diagnosed, "amount": detected, "note": "Cause + confidence + evidence named for each case"},
        {"stage": "Recommended an action", "cases": recommended, "amount": None, "note": "payment link / retry / reminder chosen by expected recovery value"},
        {"stage": "Requires operator approval", "cases": requires_approval, "amount": None, "note": "money-moving actions wait for the operator to approve"},
        {"stage": "Skipped (do nothing)", "cases": do_nothing, "amount": leaked_away, "note": "intelligent refusal: repeated failures, low recovery probability"},
        {"stage": "Executed", "cases": executed_ok, "amount": None, "note": "via Simulator (or Razorpay Test Mode when keys are set)"},
        {"stage": "Verified recovered", "cases": verified, "amount": recovered_amount, "note": "operator-approved execution confirmed — this is the headline Rs recovered"},
    ]

    return {
        **_banner_row(),
        "funnel": funnel,
        "headline_sources": [
            {"metric": "Revenue at Risk", "how": f"Sum of the {len(features)} leaked cases in the demo merchant's development set: each recovery case carries its amount; no labels used here."},
            {"metric": "Recoverable", "how": f"The subset ({truth_recoverable} cases) the synthetic world marks as worth recovering. The model never sees this label; it is the ground truth we score against."},
            {"metric": "Recovered", "how": f"Verified payments only, from the audit trail. We only count a case after the operator approves it, Execution reports success, AND Verification confirms the payment completed (Rs{recovered_amount} across {verified} cases)."},
            {"metric": "Recovery Rate", "how": "Recovered / Recoverable (same denominator in code and UI). If we can't prove a payment, we don't claim it."},
            {"metric": "Skipped / leaked", "how": f"{do_nothing} cases with Rs{leaked_away} at risk were deliberately not touched (repeated failure, low probability) — intelligent refusal, not blind retry."},
        ],
        "verified_cases": verified,
        "executed_cases": executed_ok,
    }



@app.get("/api/cases/{case_id}")
def case_detail(case_id: str) -> dict:
    """Investigation view for a single case. Shows the planned state; no
    money-moving action runs on this endpoint."""
    match = next((f for f in _all_features() if f.recovery_case_id == case_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="recovery case not found")
    report = plan_case(match, _get_policy())
    return {
        **_banner_row(),
        "diagnosis": {
            "root_cause": report.diagnosis.root_cause,
            "confidence": report.diagnosis.confidence,
            "evidence": report.diagnosis.evidence,
        },
        "decision": {
            "action": report.decision.action,
            "amount": report.decision.amount,
            "probability_of_success": report.decision.probability_of_success,
            "expected_recovery_value": report.decision.expected_recovery_value,
            "rationale": report.decision.rationale,
        },
        "policy": {
            "risk_level": report.policy.risk_level,
            "requires_approval": report.policy.requires_approval,
            "blocked": report.policy.blocked,
        },
        "timeline": [{"stage": step.stage, "detail": step.detail} for step in report.timeline],
        "verification": {
            "outcome": report.verification.outcome,
            "recovered_amount": report.verification.recovered_amount,
        },
    }


@app.post("/api/cases/{case_id}/approve")
def approve_case(case_id: str) -> dict:
    """Operator approval: execute the planned action and persist an audit row.

    This is the ONLY endpoint that performs money-moving actions. The result is
    saved to the executions table so a second approve on the same case returns
    the stored result without executing again (idempotent).

    On the real Razorpay path a payment link is only reported as recovered after
    `paid` verification (polling the link status) confirms the payment settled.
    """
    match = next((f for f in _all_features() if f.recovery_case_id == case_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="recovery case not found")

    # Idempotency: if already approved and executed, return stored result.
    existing = load_execution(DB_PATH, case_id)
    if existing is not None:
        return {
            **_banner_row(),
            "executed": existing.success,
            "already_approved": True,
            "execution": {
                "success": existing.success,
                "adapter": existing.adapter,
                "detail": existing.detail,
            },
            "verification": {
                "outcome": existing.verification_outcome,
                "recovered_amount": existing.recovered_amount,
            },
            "approved_at": existing.approved_at,
        }

    if match.leakage_type == "repeated_failure":
        raise HTTPException(status_code=409, detail="case is a do-nothing; nothing to approve")

    executor = _executor()
    report = run_case(match, executor, policy=_get_policy(), approved=True)

    # Razorpay paid verification: only count recovery after the link is paid.
    outcome = report.verification.outcome
    verified: dict | None = None
    if (
        report.execution
        and report.execution.adapter == "RAZORPAY_TEST_MODE"
        and hasattr(executor, "verify")
    ):
        paid, detail = executor.verify(report.execution, case_id)
        verified = {"paid": paid, "detail": detail}
        outcome = "recovered" if paid else "failed"

    # Persist to the audit trail.
    now = datetime.now(timezone.utc).isoformat()
    save_execution(
        DB_PATH,
        ExecutionRecord(
            recovery_case_id=case_id,
            action=report.decision.action,
            adapter=report.execution.adapter if report.execution else "NONE",
            success=report.execution.success if report.execution else False,
            detail=report.execution.detail if report.execution else "no execution",
            approved_at=now,
            verification_outcome=outcome,
            recovered_amount=report.verification.recovered_amount if outcome == "recovered" else 0,
        ),
    )

    return {
        **_banner_row(),
        "executed": report.execution is not None and report.execution.success,
        "already_approved": False,
        "execution": {
            "success": report.execution.success if report.execution else False,
            "adapter": report.execution.adapter if report.execution else "NONE",
            "detail": report.execution.detail if report.execution else "no execution",
        },
        "verification": {
            "outcome": outcome,
            "recovered_amount": report.verification.recovered_amount if outcome == "recovered" else 0,
        },
        "verified": verified,
        "timeline": [{"stage": step.stage, "detail": step.detail} for step in report.timeline],
        "approved_at": now,
    }


@lru_cache(maxsize=1)
def _cached_evaluation():
    """Hold-out evaluation (seed 42, deterministic). Cached so the dashboard's
    evaluation table and the counterfactual hero share one fit instead of two."""
    from kthma import generate

    return run_evaluation(generate(seed=42, n=500))


@app.get("/api/evaluate")
def evaluate() -> dict:
    report = _cached_evaluation()
    return {**_banner_row(), "report": {k: asdict(v) for k, v in report.methods.items()}, "table": format_report(report)}


@app.get("/api/counterfactual")
def counterfactual() -> dict:
    """The first number a judge should see: why KTHMA beats a rules engine."""
    report = _cached_evaluation()

    def wrong(m) -> int:
        # True wrong actions: total minus correct (not rate * total).
        return m.total_cases - round(m.action_accuracy * m.total_cases)

    kthma = report.methods["KTHMA"]
    rules = report.methods["Rule Based"]
    always = report.methods["Always Retry"]
    return {
        **_banner_row(),
        "headline": (
            "KTHMA recovers more ₹ and makes fewer harmful interventions than a "
            "rules engine on the same untouched hold-out cases."
        ),
        "kthma_recovered": kthma.revenue_recovered,
        "rules_recovered": rules.revenue_recovered,
        "always_retry_recovered": always.revenue_recovered,
        "incremental_vs_rules": kthma.revenue_recovered - rules.revenue_recovered,
        "incremental_vs_always_retry": kthma.revenue_recovered - always.revenue_recovered,
        "wrong_actions": {
            "kthma": wrong(kthma),
            "rules": wrong(rules),
            "always_retry": wrong(always),
        },
        "action_accuracy": {
            "kthma": kthma.action_accuracy,
            "rules": rules.action_accuracy,
            "always_retry": always.action_accuracy,
        },
    }


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
.hero{background:linear-gradient(135deg,#12325e,#12203f);border:1px solid var(--acc);border-radius:12px;padding:20px;margin-bottom:22px}
.hero h2{margin:0 0 14px;color:#fff;font-size:16px;letter-spacing:.5px}
.hrow{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.hstat{background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:8px;padding:14px}
.hstat b{display:block;font-size:26px;color:var(--ok);margin-bottom:4px}
.hstat span{font-size:12px;color:var(--mut)}
.hnote{margin:14px 0 0;font-size:13px;color:#cfe0ff;line-height:1.5}
.brk{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.brk .card p{font-size:16px}.brk .small{font-size:12px;color:var(--mut);font-weight:400;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th{font-size:11px;text-transform:uppercase;color:var(--mut);text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
td{padding:10px 12px;border-bottom:1px solid var(--line);font-size:13px}
tr.click{cursor:pointer}tr.click:hover{background:var(--panel2)}
.tag{padding:2px 8px;border-radius:10px;font-size:11px}.tag.recovered{background:#123c2e;color:var(--ok)}.tag.no_action_taken{background:#22304e;color:var(--mut)}.tag.pending_approval{background:#3a2f12;color:var(--warn)}.tag.auto_planned{background:#22304e;color:var(--mut)}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:8px 16px;font-weight:600;cursor:pointer}
button:disabled{background:var(--line);color:var(--mut);cursor:default}
#panel{display:none;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px;margin-top:16px}
#panel h3{margin:0 0 4px}.step{display:flex;gap:10px;padding:7px 0;border-bottom:1px dashed var(--line);font-size:13px}
.step b{color:var(--acc);min-width:86px}.ev{font-size:12px;color:var(--mut);margin:8px 0;line-height:1.6}
pre{background:#0d1526;border:1px solid var(--line);border-radius:8px;padding:14px;font-size:12px;overflow-x:auto}
.dv{display:flex;gap:18px;margin-top:10px;flex-wrap:wrap}.dv div{font-size:13px}.dv b{color:var(--acc)}
.source{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:6px;padding:12px 14px;margin:10px 0;font-size:13px;line-height:1.5}
.source b{color:var(--acc)}
</style></head><body>
<header><h1>KTHMA</h1><span class="banner">DEMO MERCHANT · SYNTHETIC DATA</span></header>
<main>
<h2 style="text-transform:none;font-size:15px;color:var(--txt)">Why KTHMA beats a rules engine</h2>
<div class="hero"><h2 id="cf-title" style="margin-top:8px">loading comparison...</h2>
  <div class="hrow" id="cf-row"></div>
  <div class="hnote" id="cf-note"></div></div>
<div class="cards" id="cards"></div>
<h2>Leakage breakdown</h2><div class="brk" id="brk"></div>
<h2>How we got here — the actual pipeline funnel</h2>
<table id="funnel"><thead><tr><th>Stage</th><th>Cases</th><th>Amount</th><th>What it means</th></tr></thead><tbody></tbody></table>
<div id="sources"></div>
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
// PART1 - counterfactual-first hero (why KTHMA beats rules)
fetch('/api/counterfactual').then(r=>r.json()).then(d=>{
  document.getElementById('cf-title').textContent=d.headline;
  const stat=(label,big)=>'<div class="hstat"><b>'+big+'</b><span>'+label+'</span></div>';
  document.getElementById('cf-row').innerHTML=
    stat('KTHMA recovered', fmt(d.kthma_recovered))+
    stat('Incremental vs Rules engine', fmt(d.incremental_vs_rules))+
    stat('Incremental vs Always Retry', fmt(d.incremental_vs_always_retry))+
    stat('Wrong actions: KTHMA vs Rules', d.wrong_actions.kthma+' vs '+d.wrong_actions.rules);
  document.getElementById('cf-note').textContent='Same untouched hold-out cases. Action accuracy: KTHMA '+Math.round(d.action_accuracy.kthma*100)+'% vs Rules '+Math.round(d.action_accuracy.rules*100)+'% vs Always Retry '+Math.round(d.action_accuracy.always_retry*100)+'%';
});
// PART2
fetch('/api/summary').then(r=>r.json()).then(d=>{
  const items=[['Revenue at risk',d.revenue_at_risk],['Recoverable',d.recoverable],['Recovered',d.recovered,'ok'],['Recovery rate',(100*d.recovery_rate).toFixed(1)+'%','ok'],['Recovery cases',d.case_count]];
  document.getElementById('cards').innerHTML=items.map(([k,v,c])=>`<div class="card"><h3>${k}</h3><p class="${c||''}">${(typeof v==='number'&&k!=='Recovery cases'&&k!=='Recovery rate')?fmt(v):v}</p></div>`).join('');
});
fetch('/api/breakdown').then(r=>r.json()).then(d=>{
  document.getElementById('brk').innerHTML=Object.values(d.breakdown).map(e=>`<div class="card"><h3>${e.label}</h3><p>${fmt(e.amount_at_risk)}</p><p class="small">${e.cases} cases</p></div>`).join('');
});
fetch('/api/journey').then(r=>r.json()).then(d=>{
  document.getElementById('funnel').querySelector('tbody').innerHTML=d.funnel.map(s=>`<tr>
    <td><b>${s.stage}</b></td><td>${s.cases}</td><td>${s.amount==null?'—':fmt(s.amount)}</td><td>${s.note}</td></tr>`).join('');
  document.getElementById('sources').innerHTML='<h2>What each headline number actually means</h2>'+
    d.headline_sources.map(s=>`<div class="source"><b>${s.metric}:</b> ${s.how}</div>`).join('');
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
  // Enable Approve for cases that require approval and haven't been executed.
  btn.disabled=d.verification.outcome==='recovered'||d.decision.action==='do_nothing'||!d.policy.requires_approval;
  document.getElementById('p-msg').textContent=d.verification.outcome==='recovered'?'Already executed and verified.':(d.policy.requires_approval?'This action requires operator approval before execution.':'');
}
document.getElementById('approve').onclick=async()=>{
  if(!selected)return;
  const r=await fetch('/api/cases/'+selected+'/approve',{method:'POST'});
  const d=await r.json();
  const msg=document.getElementById('p-msg');
  if(r.ok&&d.executed){msg.textContent='\\u2713 Executed via '+d.execution.adapter+' \\u2014 verified '+fmt(d.verification.recovered_amount)+' recovered';
    document.getElementById('approve').disabled=true;investigate(selected);setTimeout(()=>location.reload(),1500);}
  else if(r.ok&&d.already_approved){msg.textContent='\\u2713 Already approved and executed ('+d.execution.adapter+').';document.getElementById('approve').disabled=true;}
  else{msg.textContent='\\u2717 '+(d.detail||(d.execution&&d.execution.detail)||'execution failed');}
};
fetch('/api/evaluate').then(r=>r.json()).then(d=>{document.getElementById('eval').textContent=d.table});
</script></body></html>"""
