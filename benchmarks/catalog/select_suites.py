"""Generate a leak-safe 3DCodeBench task manifest from a pinned local dataset.

No benchmark reference factory, mesh or reference render is read or copied into
the generator-facing manifest. This is a catalog tool, not an official scorer.
Usage: python benchmarks/catalog/select_suites.py --root /path/3DCodeBench
       --dataset-revision EXACT_40_HEX_COMMIT --output /path/suites.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SOURCE = "YipengGao/3DCode/3DCodeBench"
TASK_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*_seed[0-9]+$")
SHA = re.compile(r"^[a-fA-F0-9]{40}$")


class CatalogError(ValueError):
    """Input is unavailable, invalid or unsafe for the generator."""


def _safe_file(path: Path, root: Path) -> None:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise CatalogError(f"Missing or unsafe benchmark file: {path.name}")


def discover(root: Path) -> list[dict]:
    """Discover public descriptions without reading ground-truth factory content."""
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise CatalogError("Dataset root must be an existing, non-symlink directory")
    tasks = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        name = directory.name
        if directory.is_symlink() or not TASK_ID.fullmatch(name):
            raise CatalogError(f"Unsafe or unexpected task directory: {name}")
        prompt = directory / "prompt_description.txt"
        instruction = directory / "prompt_instruction.txt"
        reference = directory / (name + ".py")
        for file in (prompt, instruction, reference):
            _safe_file(file, root)
        # Never read the factory or any reference image/mesh in this process.
        a, b = prompt.read_bytes(), instruction.read_bytes()
        if not a.strip() or not b.strip():
            raise CatalogError(f"Empty public task prompt: {name}")
        tasks.append({
            "task_id": name,
            "prompt_description_sha256": hashlib.sha256(a).hexdigest(),
            "prompt_instruction_sha256": hashlib.sha256(b).hexdigest(),
        })
    if not tasks:
        raise CatalogError("No valid 3DCodeBench categories found")
    return tasks


def select(root: Path, revision: str, curated: dict | None = None) -> dict:
    if not SHA.fullmatch(revision):
        raise CatalogError("Pin a real 40-hex Hugging Face dataset revision")
    tasks = discover(root)
    ids = {task["task_id"] for task in tasks}
    ranked = sorted(ids, key=lambda task: (hashlib.sha256(
        ("3dcodebench-suite-v1:" + task).encode()).hexdigest(), task))
    if len(ranked) < 24:
        raise CatalogError("Core tier needs at least 24 real reference task directories")
    if curated is None:
        smoke, core = ranked[:6], ranked[:24]
        selection = "deterministic_provisional_unstratified"
    else:
        smoke, core = curated.get("smoke"), curated.get("core")
        if not isinstance(smoke, list) or not isinstance(core, list):
            raise CatalogError("Curated tiers must be arrays")
        if len(smoke) != 6 or len(core) != 24 or len(set(smoke)) != 6 or len(set(core)) != 24:
            raise CatalogError("Curated tiers must contain 6/24 distinct task IDs")
        if not set(smoke).issubset(set(core)) or not set(core).issubset(ids):
            raise CatalogError("Unknown curated IDs or smoke is not a subset of core")
        selection = "explicit_curated_review_required"
    if not set(smoke).issubset(set(core)):
        raise CatalogError("Smoke set must be a subset of core")
    return {
        "schema_version": 1, "benchmark": "3DCodeBench",
        "source": SOURCE, "dataset_revision": revision.lower(),
        "blender_version": "5.0", "selection": selection,
        "reference_access": "scorer_only",
        "tiers": {"smoke": smoke, "core": core, "full": ranked if curated is None else sorted(ids)},
        "tasks": tasks,
        "note": "No factory, hidden geometry or reference media is supplied to the generator; provisional sets are not stratified.",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--dataset-revision", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--curated", type=Path, help="Optional JSON with reviewed smoke/core ID arrays")
    args = p.parse_args(argv)
    try:
        curated = json.loads(args.curated.read_text(encoding="utf-8")) if args.curated else None
        manifest = select(args.root, args.dataset_revision, curated)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists():
            raise CatalogError("Refusing to overwrite a previously frozen suite")
        args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"task_count": len(manifest["tasks"]),
                          "selection": manifest["selection"], "output": str(args.output)}))
        return 0
    except (CatalogError, OSError, ValueError) as exc:
        p.exit(2, f"Benchmark catalog failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
