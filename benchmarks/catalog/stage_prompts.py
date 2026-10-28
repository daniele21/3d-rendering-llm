"""Stage ONLY public task prompts from a pinned 3DCodeBench suite.

Never reads, copies, executes, links or exposes reference factory source, mesh
or images to the generator. Not an upstream scorer or official benchmark result.

Usage:
  python benchmarks/catalog/stage_prompts.py --dataset-root DATA/3DCodeBench \
    --suite suites.json --tier smoke --out runs/benchmark/smoke
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HEX = re.compile(r"[0-9a-f]{40}\Z")
SAFE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]*_seed[0-9]+\Z")
MAX_PROMPT_BYTES = 128 * 1024


class StagingError(ValueError):
    """Benchmark identity, task data or security boundary failed."""


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stage(dataset_root: Path, suite_path: Path, tier: str, out: Path) -> dict:
    dataset_root = Path(dataset_root)
    suite_path = Path(suite_path)
    out = Path(out)
    if tier not in ("smoke", "core", "full"):
        raise StagingError("Only smoke, core or full tiers are supported")
    if dataset_root.is_symlink() or not dataset_root.is_dir():
        raise StagingError("Dataset root must be a real directory")
    if suite_path.is_symlink() or not suite_path.is_file():
        raise StagingError("Suite manifest missing or symlinked")
    suite_bytes = suite_path.read_bytes()
    if len(suite_bytes) > 3_000_000:
        raise StagingError("Suite manifest too large")
    try:
        suite = json.loads(suite_bytes)
    except (ValueError, UnicodeError):
        raise StagingError("Invalid suite JSON") from None
    if not isinstance(suite, dict) or suite.get("benchmark") != "3DCodeBench" or suite.get("schema_version") != 1:
        raise StagingError("Unexpected benchmark suite contract")
    revision = suite.get("dataset_revision")
    if not isinstance(revision, str) or not HEX.fullmatch(revision):
        raise StagingError("Dataset revision must be pinned to an exact 40-hex commit")
    if suite.get("reference_access") != "scorer_only":
        raise StagingError("Only scorer-isolated suite supported")
    selection = suite.get("tiers", {}).get(tier)
    if not isinstance(selection, list) or not selection or len(selection) != len(set(selection)):
        raise StagingError("Missing or duplicate tier IDs")
    by_id = {t["task_id"]: t for t in suite.get("tasks", []) if isinstance(t, dict) and isinstance(t.get("task_id"), str)}
    if len(by_id) != len(suite.get("tasks", [])):
        raise StagingError("Duplicate or malformed suite tasks")
    source_root = dataset_root.resolve()
    prompts = []
    # Read and validate every source, every hash, BEFORE creating the output.
    for task_id in selection:
        if not isinstance(task_id, str) or not SAFE_ID.fullmatch(task_id) or task_id not in by_id:
            raise StagingError("Unknown or unsafe task ID")
        task_folder = dataset_root / task_id
        if task_folder.is_symlink() or not task_folder.is_dir() or not task_folder.resolve().is_relative_to(source_root):
            raise StagingError("Unsafe task directory")
        item = {"task_id": task_id, "prompts": {}}
        for file_name, hash_key in (
            ("prompt_description.txt", "prompt_description_sha256"),
            ("prompt_instruction.txt", "prompt_instruction_sha256")
        ):
            source = task_folder / file_name
            if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(source_root):
                raise StagingError("Unsafe prompt file")
            content = source.read_bytes()
            if not content.strip() or len(content) > MAX_PROMPT_BYTES:
                raise StagingError("Empty or oversized task prompt")
            expected = by_id[task_id].get(hash_key)
            if not isinstance(expected, str) or digest(content) != expected:
                raise StagingError("Prompt hash mismatch: dataset changed since catalog selection")
            try:
                text = content.decode("utf-8")
            except UnicodeError:
                raise StagingError("Prompt is not UTF-8") from None
            if "\x00" in text:
                raise StagingError("NUL in prompt")
            item["prompts"][file_name] = text
        prompts.append(item)
    if out.exists():
        raise StagingError("Refusing to overwrite or reuse a staged benchmark directory")
    if out.parent.is_symlink():
        raise StagingError("Output parent is symlinked")
    out.mkdir(parents=True, exist_ok=False)
    for item in prompts:
        folder = out / item["task_id"]
        folder.mkdir()
        for name, text in item["prompts"].items():
            (folder / name).write_text(text, encoding="utf-8")
    result = {
        "schema_version": 1, "benchmark": "3DCodeBench",
        "tier": tier, "dataset_revision": revision,
        "source_suite_sha256": digest(suite_bytes),
        "task_count": len(prompts), "task_ids": [item["task_id"] for item in prompts],
        "input_type": "public_prompt_text_only",
        "reference_access": "NONE_in_generator_workspace",
        "scoring_status": "NOT_RUN",
        "warning": "Staging prompts is NOT a scored 3DCodeBench benchmark.",
    }
    (out / "staging-manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset-root", required=True, type=Path)
    p.add_argument("--suite", required=True, type=Path)
    p.add_argument("--tier", choices=["smoke", "core", "full"], default="smoke")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        result = stage(args.dataset_root, args.suite, args.tier, args.out)
        print(json.dumps(result, sort_keys=True))
    except (OSError, StagingError, ValueError) as exc:
        p.exit(2, f"Benchmark prompt staging FAILED: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
