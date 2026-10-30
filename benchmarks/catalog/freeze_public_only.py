"""Recover EXACT original Luna benchmark public prompts with zero reference scripts.

Only downloads two generator-visible public text files per task from the
pinned Hugging Face dataset. Full 212-category prompt catalog must reproduce
the independently frozen suite SHA before the six selected prompts are
staged. No model calls, reference Python or geometry assets are downloaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from select_suites import select
from stage_prompts import stage

DATASET = "YipengGao/3DCode"
REVISION = "b70b4ee54b93fab76596da5809f3e71c617fa5c2"
EXPECTED_CATEGORIES = 212
ONLY_PUBLIC = (
    "3DCodeBench/*/prompt_description.txt",
    "3DCodeBench/*/prompt_instruction.txt",
)


def freeze_public(output: Path, selection_file: Path, *, downloader=None) -> dict:
    output = output.expanduser().absolute()
    if output.exists():
        raise ValueError("Output exists; source must be immutable and new")
    if selection_file.is_symlink() or not selection_file.is_file():
        raise ValueError("Pinned selection missing or linked")
    pinned = json.loads(selection_file.read_text(encoding="utf-8"))
    if (pinned.get("source") != DATASET
            or pinned.get("dataset_revision") != REVISION
            or not isinstance(pinned.get("smoke"), list)
            or len(pinned["smoke"]) != 6
            or len(set(pinned["smoke"])) != 6
            or not isinstance(pinned.get("expected_suite_sha256"), str)):
        raise ValueError("Pinned six tasks/revision/hash are invalid")
    if downloader is None:
        from huggingface_hub import snapshot_download
        downloader = snapshot_download

    with tempfile.TemporaryDirectory(prefix="geometry-public-prompts-only-") as td:
        downloaded = downloader(
            repo_id=DATASET, repo_type="dataset", revision=REVISION,
            allow_patterns=list(ONLY_PUBLIC),
            local_dir=Path(td) / "dataset",
        )
        root = Path(downloaded) / "3DCodeBench"
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Pinned dataset does not have public 3DCodeBench folders")
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError("Unsafe symlink in public prompt snapshot")
            if path.is_file() and path.name not in {
                "prompt_description.txt", "prompt_instruction.txt"
            }:
                raise ValueError("Non-public file unexpectedly supplied by downloader")
        # Legacy factory-based selection is intentionally bypassed *only* for
        # this prompt-only source. The exact historical suite hash is mandatory.
        initial = select(root, REVISION, require_reference=False)
        if len(initial["tasks"]) != EXPECTED_CATEGORIES:
            raise ValueError("Prompt-only dataset has not 212 canonical categories")
        smoke = pinned["smoke"]
        core = smoke + [t for t in initial["tiers"]["full"] if t not in smoke][:18]
        suite = select(
            root, REVISION, curated={"smoke":smoke,"core":core},
            require_reference=False,
        )
        suite["curation"] = "six reviewed public IDs; remaining 18 provisional hashed IDs"
        suite["release_comparable"] = False
        suite_bytes = (json.dumps(suite, indent=2, sort_keys=True) + "\n").encode()
        sha = hashlib.sha256(suite_bytes).hexdigest()
        if sha != pinned["expected_suite_sha256"]:
            raise ValueError("Public-only reconstruction differs from historical frozen suite")
        # Freeze output only after checking 212 prompts and exact historic SHA.
        output.mkdir(parents=True)
        (output / "suite.json").write_bytes(suite_bytes)
        stage(root, output / "suite.json", "smoke", output / "generator-public-smoke")
        report = {
            "schema_version":1,"data_source":DATASET,"dataset_commit":REVISION,
            "categories_verified":len(initial["tasks"]),"suite_sha256":sha,
            "public_smoke_ids":smoke,"public_prompts":12,
            "reference_files_downloaded":0,"model_calls":0,
            "source_scope":"PUBLIC_TEXT_ONLY_EXACT_SUITE_SHA",
        }
        (output / "freeze-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--selection", type=Path,
        default=Path(__file__).with_name("real_smoke_v1.json"),
    )
    a = p.parse_args()
    try:
        report = freeze_public(a.output, a.selection)
    except (ValueError, OSError) as exc:
        p.exit(2, f"Frozen public-only prompt recovery failed: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
