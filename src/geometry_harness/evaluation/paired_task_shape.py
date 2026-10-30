"""Independent per-task sampled Chamfer on verified original and five-scene evidence.

Runs unchanged, pinned upstream scorer once per task in *private isolated* result
roots. The upstream RNG then starts at the same fixed seed for each task,
independent of which other tasks previously became executable. This creates a
NEW protocol, NOT a reclassification of the historical six-task baseline.

Never executes model Python, rewrites original evidence, or makes model calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

from geometry_harness.evaluation.benchmark_evidence import EXPECTED_IDS
from geometry_harness.evaluation.counterfactual_shape import (
    ORIGINAL_VALID, TASK_IDS, diagnose_existing, _preflight, _verify_file,
)
from geometry_harness.evaluation.upstream_shape_adapter import (
    MODEL, UPSTREAM_COMMIT, ShapeGateError,
)

SEED = 0
POINTS = 8192
PROTOCOL = "LUNA_SHAPE_PINNED_SINGLE_TASK_RNG_V1"
SCORER_REL = "metrics/shape_chamfer.py"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _write(p: Path, payload: dict) -> None:
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    p.chmod(0o600)


def _safe_env() -> dict:
    return {k: v for k, v in os.environ.items() if not (
        k.endswith(("_KEY", "_TOKEN", "_SECRET"))
        or k.startswith(("GOOGLE_", "AWS_", "AZURE_"))
        or k in ("GITHUB_TOKEN", "GH_TOKEN", "GEOMETRY_CLOUD_API_KEY")
    )}


def _score_one(scorer: Path, refs: Path, root: Path, task: str,
               glb: Path, *, model: str = MODEL) -> dict:
    """One scorer process, one instance, frozen sampling configuration."""
    root.mkdir(parents=True)
    instance_root = root / "results" / "text_to_3D"
    target = instance_root / model / task / "glb"
    target.mkdir(parents=True)
    dest = target / (task + ".glb")
    shutil.copyfile(glb, dest)
    if _sha(glb) != _sha(dest) or dest.read_bytes()[:4] != b"glTF":
        raise ShapeGateError("Paired one-task generated GLB differs from verified source")
    command = [
        sys.executable, str(scorer),
        "--model", model,
        "--results-root", str(instance_root),
        "--data-root", str(refs),
        "--instances", task,
        "--n-points", str(POINTS),
        "--seed", str(SEED),
    ]
    try:
        result = subprocess.run(
            command, env=_safe_env(), capture_output=True, text=True,
            check=False, timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise ShapeGateError("Pinned one-task scorer timeout; no score fabricated") from None
    (root / "scorer-stdout.txt").write_text(result.stdout, encoding="utf-8")
    (root / "scorer-stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise ShapeGateError(f"One-task scorer failure for {task}: code={result.returncode}")
    metric_file = instance_root / model / "_metrics" / "shape_chamfer.json"
    if metric_file.is_symlink() or not metric_file.is_file():
        raise ShapeGateError(f"One-task scorer did not create metric for {task}")
    data = json.loads(metric_file.read_text(encoding="utf-8"))
    rows = data.get("per_instance")
    if (data.get("model") != model or data.get("n_instances") != 1
            or data.get("n_ok") != 1 or data.get("n_points") != POINTS
            or data.get("normalization") != "unit_sphere"
            or data.get("yaw_alignment") != [0, 90, 180, 270]
            or not isinstance(rows, list) or len(rows) != 1
            or rows[0].get("instance") != task
            or rows[0].get("status") != "OK"
            or rows[0].get("n_ref_pts") != POINTS
            or rows[0].get("n_gen_pts") != POINTS):
        raise ShapeGateError(f"Unexpected pinned one-task metric: {task}")
    record = rows[0]
    for name in ("cd", "cd_yawmin"):
        value = record.get(name)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ShapeGateError("Scorer returned invalid Chamfer")
    if record["cd_yawmin"] > record["cd"] + 1e-12:
        raise ShapeGateError("Yaw-min Chamfer exceeds unrotated Chamfer")
    return {
        "task_id": task, "status": "OK",
        "cd": record["cd"], "cd_yawmin": record["cd_yawmin"],
        "yaw_argmin": record.get("yaw_argmin"),
        "generated_glb_sha256": _sha(dest),
        "metric_sha256": _sha(metric_file),
        "metric_path": str(metric_file.relative_to(root)),
    }


def run(original: Path, baseline: Path, derived: Path, existing_stage: Path,
        upstream: Path, refs: Path, output: Path) -> dict:
    original, baseline, derived, existing_stage, upstream, refs, output = (
        p.expanduser().resolve() for p in
        (original, baseline, derived, existing_stage, upstream, refs, output)
    )
    if output.exists():
        raise ShapeGateError("New isolated per-task evidence directory required; never overwrite")
    # Validates historical/derived SHA chain, original 2/6 status, all five
    # existing exported GLBs and all six real reference hashes.
    checked = diagnose_existing(original, baseline, derived, existing_stage,
                                upstream, refs)
    if (checked["shape_status"] not in
            ("DESCRIPTIVE_5_SCENES_NOT_PAIRED", "PAIRED_5_SCENES")
            or checked["frozen_scorer_matches"] is not True
            or checked["frozen_references_match"] is not True
            or checked["five_scene_coverage_confirmed"] is not True):
        raise ShapeGateError("Untrusted historical/counterfactual evidence for per-task scorer")
    historical, previous, old, original_files, recovered = _preflight(
        original, baseline, derived)
    stage_path = existing_stage / "scorer-staging.json"
    if stage_path.is_symlink() or not stage_path.is_file():
        raise ShapeGateError("Missing trusted five-task staging inventory")
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    if stage.get("expected_tasks") != list(EXPECTED_IDS):
        raise ShapeGateError("Six-task staging cohort changed")
    by_id = {row["task_id"]: row for row in stage["tasks"]}
    if set(by_id) != set(EXPECTED_IDS) or len(stage["tasks"]) != len(EXPECTED_IDS):
        raise ShapeGateError("Duplicate or missing task")
    candidate = {}
    for task in (*ORIGINAL_VALID, *TASK_IDS):
        candidate[task] = _verify_file(existing_stage, by_id[task]["generated_glb"])
        if candidate[task].read_bytes()[:4] != b"glTF":
            raise ShapeGateError("Invalid candidate GLB")
    for task in ORIGINAL_VALID:
        if _sha(original_files[task]) != _sha(candidate[task]):
            raise ShapeGateError("Original scenes differ in baseline and candidate")
    script = upstream / SCORER_REL
    if script.is_symlink() or not script.is_file():
        raise ShapeGateError("Frozen scorer is missing")
    pinned = subprocess.run(
        ["git", "-C", str(upstream), "show", UPSTREAM_COMMIT + ":" + SCORER_REL],
        check=True, timeout=5, capture_output=True).stdout
    scorer_hash = hashlib.sha256(pinned).hexdigest()
    if scorer_hash != _sha(script) or scorer_hash != previous["upstream_shape_scorer_sha256"]:
        raise ShapeGateError("Pinned upstream scorer changed")
    output.mkdir(parents=True, mode=0o700)
    baseline_results = {}
    candidate_results = {}
    for task in EXPECTED_IDS:
        if task in ORIGINAL_VALID:
            baseline_results[task] = _score_one(
                script, refs, output / "baseline" / task, task,
                original_files[task],
            )
        if task in candidate:
            candidate_results[task] = _score_one(
                script, refs, output / "candidate" / task, task,
                candidate[task],
            )
    paired = all(
        baseline_results[t][name] == candidate_results[t][name]
        for t in ORIGINAL_VALID for name in ("cd", "cd_yawmin", "generated_glb_sha256")
    )
    rows = []
    for task in EXPECTED_IDS:
        new = candidate_results.get(task)
        old_result = baseline_results.get(task)
        rows.append({
            "task_id": task, "baseline_status": "OK" if old_result else "NO_GEN_GLB",
            "counterfactual_status": "OK" if new else "NO_GEN_GLB",
            "baseline_cd_new_protocol": old_result["cd"] if old_result else None,
            "cd": new["cd"] if new else None,
            "cd_yawmin": new["cd_yawmin"] if new else None,
            "yaw_argmin": new["yaw_argmin"] if new else None,
            "generated_glb_sha256": new["generated_glb_sha256"] if new else None,
        })
    if not paired or len(candidate_results) != 5 or len(baseline_results) != 2:
        raise ShapeGateError("Per-task same-seed paired check failed; inspect private raw outputs")
    status = "PER_TASK_RNG_ISOLATED_REPRODUCIBLE"
    report = {
        "schema_version": 1, "experiment": PROTOCOL, "status": status,
        "source_run_reclassified": False,
        "official_3dcodebench_comparable": False,
        "source_sha": historical["source_sha"],
        "dataset_revision": historical["dataset_revision"],
        "scorer_commit": UPSTREAM_COMMIT,
        "scorer_sha256": scorer_hash,
        "reference_glb_sha256": previous["reference_glb_sha256"],
        "rng_scope": "independent_process_per_instance",
        "seed": SEED, "n_points": POINTS,
        "original_native_pass": 2, "counterfactual_native_pass": 5,
        "denominator": 6, "n_baseline_scored": 2, "n_candidate_scored": 5,
        "baseline_shared_tasks_exact_match": paired,
        "baseline_cd_mean_new_protocol": sum(x["cd"] for x in baseline_results.values()) / 2,
        "candidate_cd_conditional_mean_new_protocol":
            sum(x["cd"] for x in candidate_results.values()) / 5,
        "per_instance": rows,
        "semantic_quality": "UNKNOWN_NOT_SEMANTICALLY_JUDGED",
        "new_model_calls": 0, "new_model_cost_usd": "0",
        "warning": (
            "New independent one-task RNG protocol; historical original run "
            "and its dynamic-penalty metrics are immutable and NOT directly "
            "equivalent. Both means cover different successful-task subsets. "
            "No semantic or official leaderboard quality asserted."
        ),
    }
    _write(output / "paired-one-task-chamfer.json", report)
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "baseline-stage", "derived", "existing-stage",
                 "upstream", "refs", "out"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args(argv)
    try:
        result = run(a.original, a.baseline_stage, a.derived, a.existing_stage,
                     a.upstream, a.refs, a.out)
    except (ShapeGateError, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError) as exc:
        print(f"Per-task scoring rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        k: result[k] for k in ("status", "n_baseline_scored", "n_candidate_scored",
                              "baseline_shared_tasks_exact_match",
                              "candidate_cd_conditional_mean_new_protocol",
                              "per_instance")
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
