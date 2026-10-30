"""Optional Qwen 2-task per-instance Chamfer using pinned 3DCodeBench references.

Never runs LLM code or reference factories. Requires exact verified original
CoffeeTable and explicitly counterfactual Bottle scenes, isolated reference
GLBs, pinned upstream scorer and installed Blender. A score is NEVER inferred
from a native PASS or from the counterfactual pass fraction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from geometry_harness.cli import blender_binary, sha256, ShowcaseError
from geometry_harness.evaluation.cone_counterfactual import (
    _preflight, CounterfactualError,
)
from geometry_harness.evaluation.cone_counterfactual import (
    EXPERIMENT as CONE_EXPERIMENT, TARGET, ORIGINAL_PASS,
)
from geometry_harness.evaluation.local_staged_blender import _read
from geometry_harness.evaluation.reference_provenance import (
    ARCHIVE_SHA256, ARCHIVE_SHA, BENCHMARK_SHA,
)
from geometry_harness.evaluation.upstream_shape_adapter import (
    EXPORT, UPSTREAM_COMMIT, ShapeGateError,
)
from geometry_harness.evaluation.paired_task_shape import _score_one
from geometry_harness.g1 import _safe_run
from geometry_harness.providers.local import DEFAULT_MODEL

SCORER_REL = Path("metrics/shape_chamfer.py")
TASKS = (ORIGINAL_PASS, TARGET)


def _verified_artifact(root: Path, entries: list, rel: str) -> Path:
    if not isinstance(entries, list):
        raise ShapeGateError("Missing private SHA evidence")
    found = [x for x in entries if x.get("path") == rel]
    if len(found) != 1:
        raise ShapeGateError("Missing or duplicated SHA-bound artifact")
    p = root / rel
    if (p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root)
            or p.stat().st_size != found[0].get("bytes")
            or sha256(p) != found[0].get("sha256")):
        raise ShapeGateError("SHA/size mismatch on private scene evidence")
    return p


def _verify_external_scorer(upstream: Path, refs: Path) -> tuple[Path, dict]:
    scorer = upstream / SCORER_REL
    if scorer.is_symlink() or not scorer.is_file():
        raise ShapeGateError("Missing pinned scorer script")
    try:
        commit = subprocess.run(
            ["git","-C",str(upstream),"rev-parse","HEAD"],
            check=True,timeout=10,capture_output=True,text=True,
        ).stdout.strip()
        pinned = subprocess.run(
            ["git","-C",str(upstream),"show",f"{UPSTREAM_COMMIT}:{SCORER_REL.as_posix()}"],
            check=True,timeout=10,capture_output=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        raise ShapeGateError("Unable to verify exact upstream scorer git commit") from None
    if commit != UPSTREAM_COMMIT or hashlib.sha256(pinned).hexdigest() != sha256(scorer):
        raise ShapeGateError("Upstream scorer differs from pinned source/commit")
    meta = _read(refs / "reference-provenance.json")
    if (meta.get("declared_archive_commit") != ARCHIVE_SHA
            or meta.get("archive_sha256") != ARCHIVE_SHA256
            or meta.get("published_archive_checksum_match") is not True
            or meta.get("frozen_benchmark_commit") != BENCHMARK_SHA
            or meta.get("frozen_source_download_verified_at_pinned_revision") is not True
            or meta.get("status") != "SIX_REFERENCE_PROMPTS_AND_SCRIPTS_MATCH_PINNED_DATASET"):
        raise ShapeGateError("Scorer-only references lack pinned dataset provenance")
    rows = meta.get("refs")
    if not isinstance(rows,list) or len(rows)!=6:
        raise ShapeGateError("Incomplete six-reference provenance")
    names = [r.get("task_id") for r in rows]
    if len(set(names)) != 6 or any(t not in names for t in TASKS):
        raise ShapeGateError("Missing pinned per-task references")
    for task in TASKS:
        entry = next(x for x in rows if x["task_id"]==task)
        ref = refs/task/"glb"/f"{task}.glb"
        if (ref.is_symlink() or not ref.is_file()
                or not ref.resolve().is_relative_to(refs)
                or sha256(ref)!=entry.get("reference_glb_sha256")
                or ref.stat().st_size!=entry.get("reference_glb_bytes")
                or ref.open("rb").read(4)!=b"glTF"):
            raise ShapeGateError("Scorer-only reference GLB hash/size mismatch")
    return scorer, meta


def run(stage: Path, baseline: Path, derived: Path, upstream: Path,
        refs: Path, out: Path, *, binary: str | None = None) -> dict:
    stage, baseline, derived, upstream, refs, out = (
        p.expanduser().resolve() for p in (stage, baseline, derived, upstream, refs, out)
    )
    if out.exists() or any(out.is_relative_to(root) for root in (
            stage, baseline, derived, upstream, refs)):
        raise ShapeGateError("New independent shape output required")
    _preflight(stage,baseline)
    derived_report=_read(derived/"cone-counterfactual.json")
    if (derived_report.get("experiment") != CONE_EXPERIMENT
            or derived_report.get("counterfactual_native_scene") != "PASS"
            or derived_report.get("new_model_calls") != 0
            or derived_report.get("source_stage_report_sha256") != sha256(stage/"local-benchmark.json")
            or derived_report.get("source_blender_baseline_sha256") != sha256(baseline/"local-blender-validation.json")
            or derived_report.get("source_model_output_sha256") != sha256(stage/"tasks"/TARGET/"model-generated.py")):
        raise ShapeGateError("Counterfactual source was not independently verified")
    base_report=_read(baseline/"local-blender-validation.json")
    base_record=base_report["per_instance"][0]
    if base_record.get("native_scene") != "PASS":
        raise ShapeGateError("CoffeeTable original scene was not native PASS")

    sources = {
        ORIGINAL_PASS: (
            _verified_artifact(
                baseline,base_record.get("artifact_sha256"),
                f"tasks/{ORIGINAL_PASS}/scene.blend"
            ),
            _verified_artifact(
                baseline,base_record.get("artifact_sha256"),
                f"tasks/{ORIGINAL_PASS}/geometry.json"
            ),
        ),
        TARGET: (
            _verified_artifact(
                derived,derived_report.get("artifacts"), f"tasks/{TARGET}/scene.blend"
            ),
            _verified_artifact(
                derived,derived_report.get("artifacts"), f"tasks/{TARGET}/geometry.json"
            ),
        ),
    }
    # Every independent inspector already declared a native PASS, but the
    # hashes above must match the actual source bytes used for GLB export.
    for task, (_, geometry) in sources.items():
        result = _read(geometry)
        if result.get("passed") is not True or not result.get("mesh_objects"):
            raise ShapeGateError(f"{task} independent Blender geometry missing")
    scorer, refs_meta = _verify_external_scorer(upstream, refs)
    executable = binary or blender_binary()
    if not executable:
        raise ShapeGateError("Blender is required to export independently validated scenes")

    out.mkdir(parents=True,mode=0o700)
    rows=[]
    for task in TASKS:
        scene, geometry = sources[task]
        target=out/"exports"/task
        target.mkdir(parents=True)
        measured=_read(geometry)
        expected=target/"expected.json"
        expected.write_text(json.dumps({
            "object_ids":[x["name"] for x in measured["mesh_objects"]],
        }))
        glb=target/f"{task}.glb"
        _safe_run([
            executable,"-b",str(scene),"--disable-autoexec",
            "--python-exit-code","14","--python",str(EXPORT),
            "--","--out",str(glb),"--expected",str(expected)
        ],target/"export.log",limit=120)
        if not glb.is_file() or glb.read_bytes()[:4]!=b"glTF":
            raise ShapeGateError("GLB export failed: no synthetic fallback")
        score=_score_one(scorer,refs,out/"scoring"/task,task,glb,model=DEFAULT_MODEL)
        rows.append({
            **score,
            "cohort": "unaltered_qwen" if task == ORIGINAL_PASS else "opt_in_cone_post_hoc",
            "input_scene_sha256":sha256(scene),
        })
    result={
        "schema_version":1,
        "experiment":"G1_QWEN_TWO_TASK_SHAPE_PINNED_ONE_TASK_RNG_V1",
        "model":DEFAULT_MODEL,
        "source_experiment":CONE_EXPERIMENT,
        "separate_source_cohorts":True,
        "upstream_commit":UPSTREAM_COMMIT,
        "upstream_scorer_sha256":sha256(scorer),
        "scorer_parameters":{"n_points":8192,"seed":0,"normalization":"unit_sphere","yaw_alignment":[0,90,180,270]},
        "reference_provenance_sha256":sha256(refs/"reference-provenance.json"),
        "stage_report_sha256":sha256(stage/"local-benchmark.json"),
        "baseline_validation_sha256":sha256(baseline/"local-blender-validation.json"),
        "cone_counterfactual_sha256":sha256(derived/"cone-counterfactual.json"),
        "scored_tasks":list(TASKS),"per_instance":rows,
        "n_scored":len(rows),"new_model_calls":0,"model_api_cost_usd":"0",
        "official_3dcodebench_comparable":False,
        "semantic_quality":"UNKNOWN_NOT_VISUALLY_JUDGED",
        "warning":"One-task seeded sampling; original CoffeeTable versus opt-in post-hoc Bottle. Do not merge with 1/2 original Qwen technical baseline or claim official leaderboard equivalence."
    }
    (out/"local-shape-results.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    return result


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("stage","baseline","derived","upstream","refs","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args(argv)
    try:
        result=run(a.stage,a.baseline,a.derived,a.upstream,a.refs,a.out)
    except (CounterfactualError,ShapeGateError,ShowcaseError,
            ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as e:
        print(f"Qwen shape scorer refused: {type(e).__name__}: {e}",file=sys.stderr)
        return 2
    print(json.dumps({"n_scored":result["n_scored"],
                      "per_instance":result["per_instance"]},indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
