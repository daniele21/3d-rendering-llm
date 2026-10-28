"""Single-call manual, cost-audited G1 probe; does NOT execute generated code.

This is a paid-call diagnostic, NOT a modelled/rendered Blender G1 result.
The central GitHub workflow must upload this evidence even after failure.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from geometry_harness.costs.ledger import default_ledger_path, load_events, reconcile
from geometry_harness.providers.compatible import OpenAICompatibleCodeProvider, ProviderError

PROMPT = (
    "Using Blender 5 Python bpy, create a small wooden table with a rectangular "
    "top and four separately named legs. Set sensible materials and a camera. "
    "Return only Python code; do not execute or write external files."
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    target = Path(os.environ.get("GEOMETRY_G1_PROBE_DIR",
                                 "ci-artifacts/showcase/g1")).resolve()
    ledger_path = default_ledger_path()
    if not ledger_path.is_relative_to(target):
        raise SystemExit("G1 probe ledger path must be inside owned evidence directory")
    if target.exists() and any(target.iterdir()):
        raise SystemExit("Refusing to overwrite an existing G1 cost probe bundle")
    target.mkdir(parents=True, exist_ok=True)
    outcome = "FAILED"
    error_class = None
    code_file = target / "candidate.py"
    model = os.environ.get("GEOMETRY_CLOUD_MODEL", "unknown")
    try:
        provider = OpenAICompatibleCodeProvider.from_env()
        output = provider.generate(PROMPT)
        code_file.write_text(output.code, encoding="utf-8")
        if output.pricing is None or output.pricing["status"] != "PRICED":
            raise ProviderError("Usage is incomplete or pricing is unknown")
        outcome = "SUCCEEDED_TOKEN_ACCOUNTED"
    except (ProviderError, ValueError, OSError) as exc:
        # Only log a stable error class; never raw HTTP responses or secrets.
        error_class = type(exc).__name__
    finally:
        summary = None
        if ledger_path.is_file():
            try:
                summary = reconcile(load_events(ledger_path))
                (target / "cost-summary.json").write_text(
                    json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            except (ValueError, OSError, KeyError):
                error_class = "InvalidLedger"
        if summary is None or summary["grand_total_status"] != "COMPLETE":
            outcome = "FAILED_COST_EVIDENCE"
        paths = ["costs/events.jsonl", "cost-summary.json"]
        if code_file.exists():
            paths.append("candidate.py")
        files = []
        for rel in paths:
            file = target / rel
            if file.is_file():
                files.append({"path": rel, "sha256": sha(file), "bytes": file.stat().st_size})
        manifest = {
            "schema_version": 1, "milestone": "G1-cost-probe-only",
            "outcome": outcome, "error_class": error_class,
            "source_sha": os.environ.get("SOURCE_SHA", "unknown"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "model_requested": model, "model_calls_allowed": 1,
            "render_executed": False, "files": files,
        }
        (target / "cost-probe-manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"outcome": outcome, "model": model,
                          "cost_status": None if summary is None else summary["grand_total_status"],
                          "priced_subtotal_usd": None if summary is None else summary["priced_subtotal_usd"]}))
    return 0 if outcome == "SUCCEEDED_TOKEN_ACCOUNTED" else 1


if __name__ == "__main__":
    sys.exit(main())
