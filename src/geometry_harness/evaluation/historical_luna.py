"""Operator-only, read-only retrieval + verified six-task Luna historical review.

Requires an existing user-authorized gcloud storage reader. The GitHub OIDC
identity is intentionally *ObjectCreator-only* and cannot perform this read.
Does not grant IAM, download reference factory code, or call any model.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from geometry_harness.evaluation.benchmark_evidence import audit, gallery

SOURCE_GCS=(
    "gs://project-tests-498508-geometry-showcase/geometry-harness/g1/"
    "be1a888dea819925cb855d95c18f4d75c0e934ce/"
    "40683850012-attempt-1/g1-benchmark"
)


def operate(out: Path, *, source_local: Path | None = None):
    out=out.expanduser().resolve()
    if out.exists():
        raise ValueError("Output already exists: no audit overwrite")
    if source_local is None and not shutil.which("gcloud"):
        raise RuntimeError("gcloud CLI missing; run as an authenticated private-bucket reader")
    out.mkdir(parents=True,mode=0o700)
    input_root=(out/"historical-evidence").resolve()
    if source_local is None:
        input_root.mkdir(mode=0o700)
        # No --delete / no implicit IAM mutation. The immutable original run
        # remains FAILED; we only read and audit the archived evidence.
        subprocess.run(["gcloud","storage","rsync","--recursive",SOURCE_GCS,input_root.as_posix()],
                       check=True,timeout=300)
    else:
        input_root=source_local.expanduser().resolve()
    result=audit(input_root)
    review=out/"review"
    review.mkdir(mode=0o700)
    for row in result["tasks"]:
        if row["preview_path"]:
            source=input_root/row["preview_path"]
            dest=review/row["preview_path"]
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,dest)
    (review/"audit.json").write_text(json.dumps(result,indent=2)+"\n")
    (review/"index.html").write_text(gallery(result))
    return {"original_gcs_prefix":SOURCE_GCS,
            "original_run_status":result["original_run_status"],
            "audit_status":result["audit_status"],
            "native_pass":result["native_pass"],
            "task_count":result["task_count"],
            "estimated_model_usd":result["model_estimated_usd"],
            "quality_score":"UNKNOWN_UPSTREAM_NOT_RUN",
            "review_folder":str(review)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--source-local",type=Path,
                   help="Read existing local bundle (skips any GCS access).")
    a=p.parse_args(argv)
    try:
        result=operate(a.out,source_local=a.source_local)
        print(json.dumps(result,indent=2))
        return 0
    except (OSError,ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        print("Historical evidence audit NOT VERIFIED:",type(exc).__name__,file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
