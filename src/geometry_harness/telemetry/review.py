"""Read-only run timeline and exact span ↔ cost-call ledger reconciliation.

Never display prompts, provider payloads, API keys, raw file paths or system env.
A missing or unlinked billable attempt is UNKNOWN (not zero, not a pass).
The timeline illustrates *observed* monotonic spans, NOT uninstrumented queue.
"""
from __future__ import annotations

import argparse
from collections import Counter
import html
import json
from pathlib import Path

from geometry_harness.costs.ledger import load_events, reconcile
from geometry_harness.telemetry.spans import summarize, TraceError

class ReviewError(ValueError):
    pass


def review(root: Path) -> dict:
    root=root.resolve()
    trace=root/"trace.jsonl"
    if trace.is_symlink() or not trace.is_file():
        raise ReviewError("Missing trusted run trace")
    with trace.open(encoding="utf8") as source:
        events=[json.loads(line) for line in source if line.strip()]
    report=summarize(events)
    created={}
    for event in events:
        if event["event"]=="started":
            created[event["span_id"]]=event
    finished=[event for event in events if event["event"]=="finished"]
    wall_start=min(event["monotonic_ns"] for event in created.values())
    span_times=[]
    for event in finished:
        start=created[event["span_id"]]
        span_times.append({
            "stage":start["name"],"status":event.get("status","UNKNOWN"),
            "start_ms":round((start["monotonic_ns"]-wall_start)/1e6,4),
            "elapsed_ms":round((event["monotonic_ns"]-start["monotonic_ns"])/1e6,4),
            "cost_call_id":event.get("cost_call_id"),
        })
    stage_groups=Counter()
    for item in span_times:
        stage_groups[item["stage"]]+=1
    llm=[x for x in span_times if x["stage"]=="llm.generate"]
    priced=root/"costs"/"events.jsonl"
    total=None
    billing_status="NOT_APPLICABLE" if not llm else "UNKNOWN_MISSING_LEDGER"
    if priced.exists():
        if priced.is_symlink() or not priced.is_file():
            raise ReviewError("Unsafe cost ledger")
        raw=load_events(priced)
        costs=reconcile(raw)
        total=costs["priced_subtotal_usd"]
        called={ev["call_id"] for ev in raw if ev["event"]=="started"}
        linked=[x["cost_call_id"] for x in llm if x["cost_call_id"]]
        # Every billable source must link to one and only one observed LLM span.
        if (len(linked)==len(llm)==len(called)
                and len(set(linked))==len(linked)
                and set(linked)==called
                and costs["grand_total_status"]=="COMPLETE"):
            billing_status="COMPLETE_ALL_MODEL_SPANS_RECONCILED"
        else:
            billing_status="UNKNOWN_INCOMPLETE_SPAN_COST_LINKAGE"
    return {
        "schema_version":1,"run_id":report["run_id"],
        "trace_status":report["status"],
        "observed_span_wall_ms":report["observed_wall_ms"],
        "critical_path_status":report["critical_path"],
        "critical_chain_ms":report.get("critical_chain_ms"),
        "critical_chain_stages":report.get("critical_chain_stages",[]),
        "unsettled_span_count":report["unsettled_span_count"],
        "stage_counts":dict(sorted(stage_groups.items())),
        "model_spans":len(llm),"billing_status":billing_status,
        "model_token_usd_estimate":total,
        "timeline":sorted(span_times,key=lambda x:x["start_ms"]),
        "scope":"INSTRUMENTED_STAGES_ONLY_NO_PROVIDER_QUEUE_INFERENCE",
    }


def make_html(report: dict) -> str:
    scale=max(report["observed_span_wall_ms"],.001)
    rows=[]
    for item in report["timeline"]:
        start=min(100,max(0,item["start_ms"]/scale*100))
        length=min(100-start,max(.15,item["elapsed_ms"]/scale*100))
        rows.append(
            "<tr><td>"+html.escape(item["stage"])+"</td><td>"+
            html.escape(item["status"])+"</td><td>"+
            f'{item["elapsed_ms"]:.3f}'+"</td><td><div class='rail'>"+
            f"<div class='bar' style='margin-left:{start:.3f}%;width:{length:.3f}%'></div>"+
            "</div></td></tr>"
        )
    return ("<!doctype html><html><head><meta charset='utf-8'><title>Geometry Timeline</title>"
            "<style>body{font:14px system-ui;max-width:1050px;margin:2em auto;padding:1em}"
            "table{border-collapse:collapse;width:100%}td,th{padding:9px;border-bottom:1px solid #ddd}"
            ".rail{background:#eee;width:100%;height:16px}.bar{height:16px;background:#5576a8}"
            "</style></head><body><h1>Geometry run: observed stage timeline</h1>"
            "<p>Wall ms: "+str(report["observed_span_wall_ms"])+
            " · Critical path: "+html.escape(report["critical_path_status"])+
            " · Estimated model USD: "+html.escape(str(report["model_token_usd_estimate"]))+
            " · Cost linkage: "+html.escape(report["billing_status"])+
            "</p><p>Only instrumented stages. No inferred waits or synthetic missing spans.</p>"
            "<table><tr><th>Stage</th><th>Outcome</th><th>ms</th><th>Observed time</th></tr>"+
            "".join(rows)+"</table></body></html>")


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(argv)
    if a.out.exists():
        p.error("Output directory must not exist; never replace audit evidence")
    result=review(a.root)
    a.out.mkdir(parents=True)
    (a.out/"timeline.json").write_text(json.dumps(result,indent=2)+"\n")
    (a.out/"timeline.html").write_text(make_html(result))
    print(json.dumps({k:result[k] for k in
        ("trace_status","critical_path_status","billing_status","model_token_usd_estimate")}))
    return 0 if result["billing_status"] in {"NOT_APPLICABLE","COMPLETE_ALL_MODEL_SPANS_RECONCILED"} else 2


if __name__=="__main__":
    raise SystemExit(main())
