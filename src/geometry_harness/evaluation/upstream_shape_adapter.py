"""Prepare original Luna native Blender outputs for pinned upstream shape scorer.

This stage is NOT equivalent to upstream 3DCodeBench text-to-3D: no generated
Python is executed. Original model code remains held out as non-executable.
Supports official source metrics only after independently supplied *GLB*
references and a strict pinned scorer revision. Unknown inputs stay UNKNOWN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from geometry_harness.cli import blender_binary
from geometry_harness.g1 import _safe_run
from geometry_harness.evaluation.benchmark_evidence import audit, EXPECTED_IDS
from geometry_harness.evaluation.reference_provenance import (
    ARCHIVE_SHA, BENCHMARK_SHA, ReferenceGateError,
)

UPSTREAM_COMMIT="42c7780ed3fcbd466f17f058f62e7996233777f7"
EXPORT=Path(__file__).resolve().parents[1]/"blender"/"export_verified_glb.py"
MODEL="gpt-6-luna"

class ShapeGateError(ValueError):
    pass


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(input_root: Path, output: Path, *, binary: str | None = None) -> dict:
    input_root=input_root.resolve()
    output=output.resolve()
    if output.exists():
        raise ShapeGateError("Stage output must be new")
    # Check all original file hash+cost metadata BEFORE creating output.
    verified=audit(input_root)
    executable=binary or blender_binary()
    if not executable:
        raise ShapeGateError("Blender missing: no synthetic GLB substitutions")
    output.mkdir(parents=True)
    base=output/"results"/"text_to_3D"/MODEL
    rows=[]
    for item in verified["tasks"]:
        name=item["task_id"]
        target=base/name
        target.mkdir(parents=True)
        rec={"task_id":name,"native_scene":item["native_scene"],
             "shape_status":"UNKNOWN_NO_REFERENCE","generated_glb":None,
             "original_run_status":verified["original_run_status"]}
        if item["native_scene"]=="PASS":
            source=input_root/"tasks"/name/"scene.blend"
            measured=json.loads((input_root/"tasks"/name/"geometry.json").read_text())
            expected=target/"expected.json"
            expected.write_text(json.dumps({"object_ids":[x["name"] for x in measured["mesh_objects"]]}))
            glb=target/"glb"/f"{name}.glb"
            _safe_run([executable,"-b",str(source),"--disable-autoexec",
                       "--python-exit-code","14","--python",str(EXPORT),
                       "--","--out",str(glb),"--expected",str(expected)],
                      target/"export.log",limit=120)
            if not glb.exists() or glb.read_bytes()[:4]!=b"glTF":
                raise ShapeGateError("Trusted Blender GLB export failed")
            rec["generated_glb"]={"path":str(glb.relative_to(output)),
                                  "sha256":_sha(glb),"bytes":glb.stat().st_size}
            rec["shape_status"]="READY_FOR_ISOLATED_REFERENCE_SCORER"
        rows.append(rec)
    report={"schema_version":1,"model":MODEL,
            "source_sha":verified["source_sha"],"source_cost_estimated_usd":verified["model_estimated_usd"],
            "upstream_repository":"gaoypeng/3dcodebench","upstream_commit":UPSTREAM_COMMIT,
            "dataset_revision":verified["dataset_revision"],
            "expected_tasks":list(EXPECTED_IDS),"native_pass":verified["native_pass"],
            "original_run_status":verified["original_run_status"],
            "scoring_status":"NOT_RUN_NO_REFERENCE_GLBS",
            "comparability":"NONCOMPARABLE_TO_OFFICIAL_3DCODEBENCH_GENERATED_PYTHON_EXECUTABILITY",
            "model_calls":0,"new_api_cost_estimate_usd":"0","tasks":rows}
    (output/"scorer-staging.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


def score(output: Path, upstream: Path, refs: Path) -> dict:
    output,upstream,refs=output.resolve(),upstream.resolve(),refs.resolve()
    report_file=output/"scorer-staging.json"
    if not report_file.is_file() or not (upstream/"metrics"/"shape_chamfer.py").is_file():
        raise ShapeGateError("Scorer staging and pinned upstream script required")
    report=json.loads(report_file.read_text())
    if report.get("upstream_commit")!=UPSTREAM_COMMIT:
        raise ShapeGateError("Unexpected scorer provenance")
    commit=subprocess.run(["git","-C",str(upstream),"rev-parse","HEAD"],
                          capture_output=True,text=True,timeout=5,check=True).stdout.strip()
    if commit!=UPSTREAM_COMMIT:
        raise ShapeGateError("Upstream scorer checkout is NOT the pinned commit")
    # An arbitrary GLB with the correct filename is NOT a valid benchmark
    # reference. Demand the six-sample provenance gate matching all pinned
    # upstream factory and prompt bytes, then rehash each scorer-only mesh.
    provenance_file=refs/"reference-provenance.json"
    if provenance_file.is_symlink() or not provenance_file.is_file():
        raise ShapeGateError("Verified scorer-only reference provenance required")
    provenance=json.loads(provenance_file.read_text(encoding="utf-8"))
    if (provenance.get("schema_version") != 1
        or provenance.get("status") !=
            "SIX_REFERENCE_PROMPTS_AND_SCRIPTS_MATCH_PINNED_DATASET"
        or provenance.get("frozen_source_download_verified_at_pinned_revision") is not True
        or provenance.get("declared_archive_commit") != ARCHIVE_SHA
        or provenance.get("frozen_benchmark_commit") != BENCHMARK_SHA
        or not isinstance(provenance.get("archive_sha256"),str)
        or len(provenance["archive_sha256"]) != 64):
        raise ShapeGateError("Reference archive prompt/factory revision provenance unverified")
    reference_rows=provenance.get("refs")
    if not isinstance(reference_rows,list) or len(reference_rows) != len(EXPECTED_IDS):
        raise ShapeGateError("Missing six pinned reference mesh identities")
    reference_by_id={x.get("task_id"):x for x in reference_rows if isinstance(x,dict)}
    if len(reference_by_id) != len(EXPECTED_IDS) or set(reference_by_id) != set(EXPECTED_IDS):
        raise ShapeGateError("Unexpected reference category list")
    # Supplied reference meshes are scorer-only. We NEVER execute factory code.
    ref_inventory=[]
    for name in EXPECTED_IDS:
        file=refs/name/"glb"/f"{name}.glb"
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(refs) or file.read_bytes()[:4]!=b"glTF":
            raise ShapeGateError("All six real scorer-private reference GLBs are required")
        if (_sha(file) != reference_by_id[name].get("reference_glb_sha256")
            or file.stat().st_size != reference_by_id[name].get("reference_glb_bytes")):
            raise ShapeGateError("Reference mesh does not match validated archive manifest")
        ref_inventory.append({"task_id":name,"sha256":_sha(file)})
    script=upstream/"metrics"/"shape_chamfer.py"
    # A pinned HEAD alone is insufficient: local tracked files can be edited.
    # Verify the exact scorer script blob at the frozen commit before running
    # any third-party Python in the isolated scorer environment.
    expected_source=subprocess.run(
        ["git","-C",str(upstream),"show",UPSTREAM_COMMIT+":metrics/shape_chamfer.py"],
        capture_output=True, timeout=5, check=True).stdout
    if _sha(script) != hashlib.sha256(expected_source).hexdigest():
        raise ShapeGateError("Pinned upstream scorer script modified or inconsistent with Git commit")
    target=output/"results"/"text_to_3D"
    # Disable network-dependent environment secrets in the scorer process.
    env={k:v for k,v in os.environ.items() if not (
        k.endswith(("_KEY","_TOKEN","_SECRET")) or k.startswith(("GOOGLE_","AWS_","AZURE_"))
    )}
    cmd=[sys.executable,str(script),"--model",MODEL,
         "--results-root",str(target),"--data-root",str(refs),
         "--instances",*EXPECTED_IDS,"--n-points","8192","--seed","0"]
    completed=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=180,check=False)
    if completed.returncode:
        raise ShapeGateError(f"Pinned scorer failed: exit={completed.returncode}; no metric fabricated")
    metric=target/MODEL/"_metrics"/"shape_chamfer.json"
    if not metric.is_file():
        raise ShapeGateError("Scorer did not produce its documented metric file")
    result=json.loads(metric.read_text())
    if result.get("n_instances")!=len(EXPECTED_IDS):
        raise ShapeGateError("Scorer silently changed six-task denominator")
    profile={"schema_version":1,"upstream_commit":UPSTREAM_COMMIT,
             "upstream_shape_scorer_sha256":_sha(script),
             "dataset_revision":report["dataset_revision"],
             "reference_glb_sha256":ref_inventory,
             "reference_provenance_status":provenance["status"],
             "reference_archive_sha256":provenance["archive_sha256"],
             "original_run_status":report["original_run_status"],
             "n_instances":result["n_instances"],"n_scored":result["n_ok"],
             "conditional_mean":result["cd"]["conditional_mean"],
             "penalized_mean":result["cd"]["penalized_mean"],
             "scorer_status":"UPSTREAM_SHAPE_CHAMFER_EXECUTED",
             "comparability":"NONCOMPARABLE_5_2_BLENDER_AND_RESTRICTED_AST",
             "model_calls":0,"new_model_cost_estimated_usd":"0"}
    (output/"shape-scorer-provenance.json").write_text(json.dumps(profile,indent=2)+"\n")
    return profile


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--upstream",type=Path)
    p.add_argument("--refs",type=Path)
    a=p.parse_args(argv)
    if (a.upstream is None)!=(a.refs is None):
        p.error("Provide both upstream and scorer-private GLB reference root to score")
    if a.input:
        result=stage(a.input,a.out)
    else:
        if not a.out.is_dir():
            p.error("--input required for new evidence stage")
        result=json.loads((a.out/"scorer-staging.json").read_text())
    if a.upstream:
        result=score(a.out,a.upstream,a.refs)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
