"""Auditable paired benchmark reporting, preserving FAIL and UNKNOWN.

Input JSON is {"records": [EvaluationRecord, ...]}; no simulated scores,
vendor model calls or benchmark ground-truth are involved. Intended as a
reporting foundation; it does not claim equivalence to official scorers.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import html
import json
from pathlib import Path
from typing import Any


class EvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationRecord:
    task_id: str
    suite_revision: str
    arm: str
    model: str
    blender_version: str
    status: str
    source_sha: str
    duration_seconds: float
    cost_usd: float | None = None
    visual_score: float | None = None
    geometry_status: str = "UNKNOWN"
    run_id: str = ""

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "EvaluationRecord":
        if not isinstance(raw, dict):
            raise EvaluationError("Each record must be an object")
        required = ("task_id", "suite_revision", "arm", "model", "blender_version",
                    "source_sha", "status", "duration_seconds")
        if any(not raw.get(k) and raw.get(k) != 0 for k in required):
            raise EvaluationError("Missing benchmark identity, status or duration")
        if raw["status"] not in ("PASS", "FAIL", "UNKNOWN"):
            raise EvaluationError("Status must be PASS, FAIL or UNKNOWN")
        if raw.get("geometry_status", "UNKNOWN") not in ("PASS", "FAIL", "UNKNOWN"):
            raise EvaluationError("Unknown geometry status")
        for key in ("duration_seconds", "cost_usd", "visual_score"):
            value = raw.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise EvaluationError(f"{key} must be a number or null")
            if value is not None and (not (float("-inf") < float(value) < float("inf")) or
                                      float(value) < 0):
                raise EvaluationError(f"{key} must be finite and non-negative")
        if raw.get("visual_score") is not None and float(raw["visual_score"]) > 1:
            raise EvaluationError("Visual score must be 0..1, or UNKNOWN")
        return cls(**{k: raw[k] for k in required},
                   cost_usd=raw.get("cost_usd"),
                   visual_score=raw.get("visual_score"),
                   geometry_status=raw.get("geometry_status", "UNKNOWN"),
                   run_id=raw.get("run_id", ""))


def compare(records: list[EvaluationRecord], baseline: str, candidate: str) -> dict:
    if baseline == candidate:
        raise EvaluationError("Baseline and candidate must differ")
    pairs: dict[str, dict[str, EvaluationRecord]] = defaultdict(dict)
    keys = set()
    for record in records:
        if record.arm not in (baseline, candidate):
            continue
        if (record.task_id, record.arm) in keys:
            raise EvaluationError(f"Duplicate run for {record.task_id}/{record.arm}; repetitions need explicit grouping")
        keys.add((record.task_id, record.arm))
        pairs[record.task_id][record.arm] = record
    matched = []
    excluded = []
    for task_id, arms in sorted(pairs.items()):
        if set(arms) != {baseline, candidate}:
            excluded.append({"task_id": task_id, "reason": "missing_arm",
                             "available": sorted(arms)})
            continue
        a, b = arms[baseline], arms[candidate]
        if (a.suite_revision, a.model, a.blender_version) != (b.suite_revision, b.model, b.blender_version):
            excluded.append({"task_id": task_id, "reason": "unpaired_configuration"})
            continue
        matched.append((a, b))
    if not matched:
        raise EvaluationError("No matched tasks with comparable suite/model/Blender settings")

    def summarize(col: int) -> dict:
        xs = [pair[col] for pair in matched]
        accepted = sum(x.status == "PASS" for x in xs)
        known_costs = [float(x.cost_usd) for x in xs if x.cost_usd is not None]
        known_visual = [float(x.visual_score) for x in xs if x.visual_score is not None]
        return {
            "attempts": len(xs),
            "pass_count": accepted, "fail_count": sum(x.status == "FAIL" for x in xs),
            "unknown_count": sum(x.status == "UNKNOWN" for x in xs),
            "pass_rate": accepted / len(xs),
            "geometry_pass_count": sum(x.geometry_status == "PASS" for x in xs),
            "mean_seconds": sum(x.duration_seconds for x in xs) / len(xs),
            "cost_usd_total": sum(known_costs) if len(known_costs) == len(xs) else None,
            "cost_per_accepted_usd": (sum(known_costs) / accepted) if len(known_costs) == len(xs) and accepted else None,
            "visual_score_mean_known_only": sum(known_visual) / len(known_visual) if known_visual else None,
            "visual_scored_count": len(known_visual),
        }

    return {
        "schema_version": 1, "baseline": baseline, "candidate": candidate,
        "matched_tasks": len(matched), "excluded_tasks": excluded,
        "arms": {baseline: summarize(0), candidate: summarize(1)},
        "pairs": [{
            "task_id": a.task_id,
            "baseline_status": a.status, "candidate_status": b.status,
            "baseline_geometry": a.geometry_status,
            "candidate_geometry": b.geometry_status,
            "baseline_visual": a.visual_score, "candidate_visual": b.visual_score,
            "baseline_run_id": a.run_id, "candidate_run_id": b.run_id,
        } for a, b in matched],
        "warning": "Descriptive paired report; not an official 3DCodeBench score or statistical significance claim.",
    }


def html_report(report: dict) -> str:
    esc = lambda x: html.escape(str(x), quote=True)
    header = "<tr><th>Task</th><th>Baseline</th><th>Candidate</th><th>Geometry A/B</th><th>Visual A/B</th></tr>"
    rows = []
    for pair in report["pairs"]:
        visual = lambda x: "UNKNOWN" if x is None else f"{x:.3f}"
        rows.append("<tr>" + "".join("<td>" + esc(cell) + "</td>" for cell in (
            pair["task_id"], pair["baseline_status"], pair["candidate_status"],
            f'{pair["baseline_geometry"]} / {pair["candidate_geometry"]}',
            f'{visual(pair["baseline_visual"])} / {visual(pair["candidate_visual"])}',
        )) + "</tr>")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<title>Geometry benchmark comparison</title><style>"
            "body{font:16px system-ui;max-width:1000px;margin:3em auto;padding:1em}"
            "table{border-collapse:collapse;width:100%}th,td{padding:.6em;border:1px solid #aaa}"
            "</style><h1>Paired 3D benchmark report</h1><p>"
            + esc(report["warning"]) + "</p><p>Matched: "
            + str(report["matched_tasks"]) + " / Excluded: "
            + str(len(report["excluded_tasks"])) + "</p><table>"
            + header + "".join(rows) + "</table></html>")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--baseline", default="direct")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        records = [EvaluationRecord.parse(raw) for raw in json.loads(args.input.read_text())["records"]]
        report = compare(records, args.baseline, args.candidate)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.output / "index.html").write_text(html_report(report))
        print(json.dumps({"matched": report["matched_tasks"], "output": str(args.output)}))
        return 0
    except (EvaluationError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Evaluation failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
