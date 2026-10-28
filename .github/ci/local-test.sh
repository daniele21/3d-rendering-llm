#!/usr/bin/env bash
set -euo pipefail

# Executed ONLY by daniele21/local-runner-infra on an explicitly trusted, exact SHA.
# Repository-owned validation. No downloads, secrets or cloud-model calls.
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "::error::Geometry Harness local lane requires macOS ARM64 (Mac mini)" >&2
  exit 2
fi

mkdir -p ci-artifacts/showcase
python3 - <<'PY'
import json
import os
import pathlib
import platform
import shutil
from datetime import datetime, timezone

out = pathlib.Path("ci-artifacts/showcase")
report = {
    "evidence_type": "runner_preflight_only",
    "geometry_demo_executed": False,
    "source_repo": os.environ.get("SOURCE_REPO", "unknown"),
    "source_sha": os.environ.get("SOURCE_SHA", "unknown"),
    "runner_os": platform.system(),
    "runner_arch": platform.machine(),
    "python": platform.python_version(),
    "blender_on_path": bool(shutil.which("blender")),
    "uv_on_path": bool(shutil.which("uv")),
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
}
(out / "runner-preflight.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

# G0 is a deliberate boundary: docs-only validation is NOT a Blender demo.
# After pyproject.toml appears, only an actual G0 Blender showcase can pass this lane.
if [[ -f pyproject.toml ]]; then
  export PYTHONPATH="$PWD/src"
  python3 -m geometry_harness doctor
  python3 -m unittest discover -s tests -p 'test_g0_contract.py' -v
  GEOMETRY_SHOWCASE_DIR="$PWD/ci-artifacts/showcase/g0" \
    python3 -m unittest discover -s tests/e2e -p 'test_showcase_g0.py' -v
  python3 -m geometry_harness showcase validate ci-artifacts/showcase/g0
  # This is a REAL Blender test of a trusted static source fixture, NOT a model run.
  GEOMETRY_G1_FIXTURE_DIR="$PWD/ci-artifacts/showcase/g1-fixture" \
    python3 -m unittest discover -s tests/e2e -p 'test_showcase_g1_fixture.py' -v
  GEOMETRY_G1_CYLINDER_DIR="$PWD/ci-artifacts/showcase/g1-cylinder-fixture" \
    python3 -m unittest discover -s tests/e2e -p 'test_g1_primitives.py' -v
  echo "G1 cylinders and spheres verified with real Blender; zero model calls."
  echo "G1 safe AST->Blender fixture verified with zero model calls."
  GEOMETRY_VAL_FIXTURE_DIR="$PWD/ci-artifacts/showcase/val-fixture" \
    python3 -m unittest discover -s tests/e2e -p 'test_validation_real_blender.py' -v
  echo "VAL-01 four-view real Blender + typed geometry tests verified."
  GEOMETRY_REPAIR_FIXTURE_DIR="$PWD/ci-artifacts/showcase/repair-fixture" \
    python3 -m unittest discover -s tests/e2e -p 'test_scoped_repair_blender.py' -v
  echo "EDIT-01 native single-object repair and source-preserving rollback verified."
  GEOMETRY_SHAPE_FIXTURE_DIR="$PWD/ci-artifacts/showcase/glb-fixture" \
    python3 -m unittest discover -s tests/e2e -p 'test_native_glb_export.py' -v
  echo "BH-02 GLB export validated, no scorer scripts/AI executed."
  echo "G0 verified on real Blender; outputs in ci-artifacts/showcase/g0."
  exit 0
fi

# Current source is still the repo-template-sw distribution. Validate it as such;
# do not pretend a 3D app or actual milestone showcase has been executed.
python3 template/scripts/verify_repository.py --root template --template-mode
python3 template/scripts/verify_operations.py --root template --template-mode
python3 template/scripts/verify_validation_cadence.py --root template --template-mode
python3 template/scripts/verify_e2e.py --root template --template-mode
python3 template/scripts/verify_stage_environment_policy.py --root template --template-mode
python3 template/scripts/verify_infrastructure.py --root template --template-mode
python3 template/scripts/verify_product_development.py --root template --template-mode
python3 template/scripts/verify_product_experience.py --root template --template-mode
python3 template/scripts/verify_docs.py --root template --template-mode
python3 template/scripts/verify_agent_context.py --root template --template-mode
python3 -m unittest discover -s tests -v
python3 -m py_compile template/scripts/*.py
echo "Preflight complete: engineering template checks only. No G0 geometry milestone claimed."
