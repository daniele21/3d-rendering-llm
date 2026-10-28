"""Fetch and validate the actual 3DCodeBench dataset revision, isolate prompts.

Network only on the explicitly enabled benchmark-data CI lane. NEVER runs
reference Blender Python; full dataset downloaded into a separate scorer-only
temp directory, generator gets ONLY two public prompt texts per selected task.
No OpenAI calls. A staging manifest is NOT a benchmark score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from select_suites import select
from stage_prompts import stage

DATASET = "YipengGao/3DCode"
REVISION = "b70b4ee54b93fab76596da5809f3e71c617fa5c2"
EXPECTED_CATEGORIES = 212


def freeze(output: Path, selection_file: Path):
    # Explicit dataset commitment; never allow an unpinned "main" pull.
    pinned = json.loads(selection_file.read_text(encoding="utf-8"))
    if pinned.get("dataset_revision") != REVISION or pinned.get("source") != DATASET:
        raise ValueError("Suite source/dataset pin changed: review upstream before proceeding")
    smoke = pinned.get("smoke")
    if not isinstance(smoke, list) or len(smoke) != 6 or len(set(smoke)) != 6:
        raise ValueError("Six reviewed smoke task IDs required")
    if output.exists():
        raise ValueError("Refusing to overwrite existing benchmark evidence")
    from huggingface_hub import snapshot_download
    with tempfile.TemporaryDirectory(prefix="3dcodebench-scorer-only-") as private:
        # Source reference scripts stay ONLY in private, never in generator output.
        root = Path(snapshot_download(
            repo_id=DATASET, repo_type="dataset", revision=REVISION,
            allow_patterns=["3DCodeBench/**"],
            local_dir=Path(private) / "dataset",
        )) / "3DCodeBench"
        # Initial pinned categories are discovered with NO script reads.
        initial = select(root, REVISION)
        if len(initial["tasks"]) != EXPECTED_CATEGORIES:
            raise ValueError(f"Expected 212 canonical categories, got {len(initial['tasks'])}")
        core = smoke + [t for t in initial["tiers"]["full"] if t not in smoke][:18]
        suite = select(root, REVISION, curated={"smoke": smoke, "core": core})
        suite["curation"] = "six reviewed public IDs; remaining 18 provisional hashed IDs"
        suite["release_comparable"] = False
        output.mkdir(parents=True)
        suite_file = output / "suite.json"
        suite_file.write_text(json.dumps(suite, indent=2, sort_keys=True) + "\n")
        public = stage(root, suite_file, "smoke", output / "generator-public-smoke")
        assert public["task_ids"] == smoke
        report = {
            "schema_version": 1, "data_source": DATASET,
            "dataset_commit": REVISION,
            "categories_verified": len(initial["tasks"]),
            "suite_sha256": hashlib.sha256(suite_file.read_bytes()).hexdigest(),
            "public_smoke_ids": smoke,
            "public_prompts": len(smoke) * 2,
            "hidden_reference_scripts_exported": 0,
            "model_calls": 0,
            "scorer_status": "NOT_RUN",
            "licensing": "dataset card MIT; original Infinigen factory provenance BSD-3; verify redistribution terms",
            "warning": "Public data freeze only; no model or official quality metric.",
        }
        (output / "freeze-report.json").write_text(json.dumps(report, indent=2) + "\n")
        return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--selection", type=Path, default=Path(__file__).with_name("real_smoke_v1.json"))
    a = p.parse_args()
    result = freeze(a.output, a.selection)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
