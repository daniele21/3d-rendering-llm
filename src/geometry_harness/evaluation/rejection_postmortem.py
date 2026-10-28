"""Read-only Luna six-task parser-failure postmortem, with optional name-only ablation.

ONLY reads already verified, private historic model output. Never executes model
Python, calls a provider, retries a paid run or changes the original results.
An alias-only compiler PASS is NOT a Blender scene PASS or upstream quality score.
The candidate must pass the EXACT same production safe-AST parser.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

from geometry_harness.evaluation.benchmark_evidence import audit
from geometry_harness.strategies.bpy_subset import compile_bpy_subset, UnsafeGeneratedCode

TASK_IDS = ("AquariumTank_seed0", "ArmChair_seed0", "Bottle_seed0")
_SAFE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")


class PostmortemError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _alias(raw: str, index: int) -> str:
    if not isinstance(raw, str) or not raw or len(raw) > 128 or any(
        ord(char) < 32 or char in "/\\" for char in raw
    ):
        raise PostmortemError("Invalid name is not eligible for name-only ablation")
    ascii_name = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_name).strip("_-")
    if not slug:
        slug = f"part_{index}"
    if not slug[0].isalpha():
        slug = "part_" + slug
    slug = slug[:48].rstrip("_-")
    if not _SAFE_NAME.fullmatch(slug):
        raise PostmortemError("Cannot construct an allowed object alias")
    return slug


def inspect(source: str) -> tuple[dict, str | None]:
    """Check original, replace ONLY invalid literal .name values in AST copy.

    No full-program normalization, no safety bypass, no build or execution.
    """
    try:
        compile_bpy_subset(source)
        original_status, first_error = "COMPILER_PASS", None
    except UnsafeGeneratedCode as exc:
        original_status, first_error = "COMPILER_FAIL", str(exc)
    data = {
        "original_compiler_status": original_status,
        "original_compiler_error": first_error,
        "name_ablation_status": "NOT_APPLICABLE",
        "name_ablation_compiler_error": None,
        "invalid_names": [],
        "candidate_source_sha256": None,
        "candidate_object_count": None,
        "native_scene_after_ablation": "NOT_RUN",
        "official_quality_score": None,
    }
    try:
        tree = ast.parse(source)
    except SyntaxError:
        data["name_ablation_status"] = "UNAVAILABLE_INVALID_PYTHON"
        return data, None
    modifications = []
    used = []
    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Attribute) or target.attr != "name":
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        assignments.append((node, node.value.value))
        if _SAFE_NAME.fullmatch(node.value.value):
            used.append(node.value.value)
    for index, (node, name) in enumerate(assignments, 1):
        if _SAFE_NAME.fullmatch(name):
            continue
        entry = {"line": node.lineno, "original_name": name, "suggested_alias": None}
        data["invalid_names"].append(entry)
        try:
            alias = _alias(name, index)
        except PostmortemError:
            data["name_ablation_status"] = "BLOCKED_UNSAFE_NAME"
            return data, None
        if alias in used:
            data["name_ablation_status"] = "BLOCKED_COLLIDING_ALIAS"
            return data, None
        used.append(alias)
        entry["suggested_alias"] = alias
        modifications.append((node, alias))
    if not modifications:
        data["name_ablation_status"] = "NOT_APPLICABLE_NO_INVALID_LITERAL_NAMES"
        return data, None
    for node, alias in modifications:
        # The AST structure remains identical: only the string constant in
        # a literal object-name assignment is replaced with a safe alias.
        node.value.value = alias
    candidate = ast.unparse(tree) + "\n"
    data["candidate_source_sha256"] = _sha(candidate.encode("utf-8"))
    try:
        spec = compile_bpy_subset(candidate)
    except UnsafeGeneratedCode as exc:
        data["name_ablation_status"] = "COMPILER_FAIL_AFTER_NAME_ABLATION"
        data["name_ablation_compiler_error"] = str(exc)
        return data, None
    data["name_ablation_status"] = "COMPILER_PASS_AFTER_NAME_ABLATION"
    data["candidate_object_count"] = len(spec["objects"])
    return data, candidate


def run(bundle: Path, output: Path) -> dict:
    bundle = bundle.expanduser().resolve()
    output = output.expanduser().resolve()
    if output.exists():
        raise PostmortemError("Refusing to replace existing private evidence")
    verified = audit(bundle)  # Original source hashes, six tasks & costs first.
    output.mkdir(mode=0o700, parents=True)
    rows = []
    for task in TASK_IDS:
        path = bundle / "tasks" / task / "model-generated.py"
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(bundle):
            raise PostmortemError("Original task code missing or untrusted")
        raw = path.read_bytes()
        if len(raw) > 160_000:
            raise PostmortemError("Generated code exceeds permitted source limit")
        source = raw.decode("utf-8")
        finding, candidate = inspect(source)
        row = {"task_id": task, "original_source_sha256": _sha(raw), **finding}
        if candidate:
            # Derived fixture is NOT original run evidence. Keep it outside
            # original bundle. No automatic native Blender invocation.
            dest = output / f"{task}.alias-ablation.py"
            dest.write_text(candidate, encoding="utf-8")
            dest.chmod(0o600)
            row["derived_candidate_filename"] = dest.name
        rows.append(row)
    report = {
        "schema_version": 1,
        "source_run_status": verified["original_run_status"],
        "source_evidence_status": verified["audit_status"],
        "source_model": verified["model"],
        "source_dataset_revision": verified["dataset_revision"],
        "source_native_pass": verified["native_pass"],
        "source_task_count": verified["task_count"],
        "source_model_cost_usd_estimate": verified["model_estimated_usd"],
        "postmortem_model_calls": 0,
        "postmortem_usd": "0",
        "interpretation": "Compiler-only name ablation; never revise original 2/6, never count new scene PASS without real Blender.",
        "results": rows,
    }
    (output / "postmortem.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "postmortem.json").chmod(0o600)
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = run(args.bundle, args.out)
    except (PostmortemError, ValueError, OSError, UnicodeError) as exc:
        print(f"Postmortem rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"historical_scene_pass": result["source_native_pass"],
                      "historical_task_count": result["source_task_count"],
                      "findings": [{
                          "task": item["task_id"],
                          "invalid_names": item["invalid_names"],
                          "name_only_result": item["name_ablation_status"],
                          "secondary_error": item["name_ablation_compiler_error"]
                      } for item in result["results"]]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
