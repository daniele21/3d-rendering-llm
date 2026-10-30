"""Offline tests: frozen public-only reconstruction never fetches references."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "catalog"
sys.path.insert(0, str(ROOT))

from select_suites import select, discover, CatalogError


def load():
    spec = importlib.util.spec_from_file_location(
        "freeze_public_only", ROOT / "freeze_public_only.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


freeze = load()


def make_public(root: Path, count: int = 30):
    for i in range(count):
        tid = f"Demo{i:02d}_seed0"
        folder = root / tid
        folder.mkdir()
        (folder / "prompt_description.txt").write_text(f"public shape {i}")
        (folder / "prompt_instruction.txt").write_text(f"build shape {i}")


def pinned_fixture(tmp: Path):
    dataset = tmp / "snapshot" / "3DCodeBench"
    dataset.mkdir(parents=True)
    make_public(dataset)
    provisional = select(dataset, freeze.REVISION, require_reference=False)
    smoke = sorted(provisional["tiers"]["full"][:6])
    core = smoke + [x for x in provisional["tiers"]["full"] if x not in smoke][:18]
    suite = select(
        dataset, freeze.REVISION, {"smoke":smoke,"core":core},
        require_reference=False,
    )
    suite["curation"] = "six reviewed public IDs; remaining 18 provisional hashed IDs"
    suite["release_comparable"] = False
    digest = hashlib.sha256(
        (json.dumps(suite, indent=2, sort_keys=True) + "\n").encode()
    ).hexdigest()
    selection = tmp / "pinned.json"
    selection.write_text(json.dumps({
        "source":freeze.DATASET,"dataset_revision":freeze.REVISION,
        "smoke":smoke,"expected_suite_sha256":digest,
    }))
    return dataset, selection


class PublicOnlyRecoveryTests(unittest.TestCase):
    def test_public_dataset_without_reference_factories_is_explicitly_supported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_public(root)
            with self.assertRaises(CatalogError):
                discover(root)
            self.assertEqual(len(discover(root, require_reference=False)), 30)
            with self.assertRaises(CatalogError):
                select(root, freeze.REVISION)
            self.assertEqual(len(select(root, freeze.REVISION, require_reference=False)["tasks"]),30)

    def test_exact_frozen_suite_reproduces_without_factory_downloads(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dataset, pin = pinned_fixture(root)
            calls = []
            def downloader(**kw):
                calls.append(kw)
                return str(dataset.parent)
            with patch.object(freeze,"EXPECTED_CATEGORIES",30):
                report=freeze.freeze_public(root/"out",pin,downloader=downloader)
            self.assertEqual(len(calls),1)
            self.assertEqual(set(calls[0]["allow_patterns"]),set(freeze.ONLY_PUBLIC))
            self.assertEqual(report["public_prompts"],12)
            self.assertEqual(report["reference_files_downloaded"],0)
            self.assertEqual(
                hashlib.sha256((root/"out"/"suite.json").read_bytes()).hexdigest(),
                report["suite_sha256"],
            )
            self.assertTrue((root/"out"/"generator-public-smoke"/"staging-manifest.json").exists())
            allfiles = list((root/"out"/"generator-public-smoke").rglob("*"))
            self.assertTrue(all(not p.is_file() or p.name in {
                "prompt_description.txt", "prompt_instruction.txt",
                "staging-manifest.json",
            } for p in allfiles))

    def test_wrong_hash_blocks_output_without_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dataset,pin=pinned_fixture(root)
            p=json.loads(pin.read_text())
            p["expected_suite_sha256"]="0"*64
            pin.write_text(json.dumps(p))
            with patch.object(freeze,"EXPECTED_CATEGORIES",30):
                with self.assertRaisesRegex(ValueError,"differs from historical"):
                    freeze.freeze_public(root/"out",pin,downloader=lambda **_:str(dataset.parent))
            self.assertFalse((root/"out").exists())

    def test_reference_script_in_download_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dataset,pin=pinned_fixture(root)
            (dataset/"Demo00_seed0"/"Demo00_seed0.py").write_text("PRIVATE")
            with patch.object(freeze,"EXPECTED_CATEGORIES",30):
                with self.assertRaisesRegex(ValueError,"Non-public"):
                    freeze.freeze_public(root/"out",pin,downloader=lambda **_:str(dataset.parent))
            self.assertFalse((root/"out").exists())


if __name__=="__main__":
    unittest.main()
