"""Offline exact-revision public-prompt staging tests, no third-party access."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "catalog"
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
selector = load("select_suites")
stager = load("stage_prompts")


def make(root, count=30):
    for i in range(count):
        tid = f"Demo{i:02d}_seed0"
        p = root / tid
        p.mkdir()
        (p / "prompt_description.txt").write_text(f"Make public shape {i}", encoding="utf8")
        (p / "prompt_instruction.txt").write_text(f"Build shape {i}", encoding="utf8")
        (p / f"{tid}.py").write_text("THIS_IS_PRIVATE_SCORER_REFERENCE = 42", encoding="utf8")


class PublicPromptStagingTests(unittest.TestCase):
    def prepare(self, root):
        make(root)
        manifest = root.parent / "suite.json"
        manifest.write_text(json.dumps(selector.select(root, "a" * 40)), encoding="utf-8")
        return manifest

    def test_exact_six_and_reference_never_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "dataset"
            root.mkdir()
            suite = self.prepare(root)
            out = base / "public_generator"
            summary = stager.stage(root, suite, "smoke", out)
            self.assertEqual(summary["task_count"], 6)
            self.assertEqual(summary["reference_access"], "NONE_in_generator_workspace")
            self.assertEqual(summary["scoring_status"], "NOT_RUN")
            files = {p.name for p in out.rglob("*") if p.is_file()}
            self.assertEqual(files, {"prompt_description.txt", "prompt_instruction.txt",
                                      "staging-manifest.json"})
            self.assertNotIn("THIS_IS_PRIVATE_SCORER_REFERENCE",
                             "".join(p.read_text() for p in out.rglob("*") if p.is_file()))
            with self.assertRaisesRegex(stager.StagingError, "overwrite"):
                stager.stage(root, suite, "smoke", out)

    def test_tampered_public_prompt_refuses_to_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "dataset"
            root.mkdir()
            suite = self.prepare(root)
            first = json.loads(suite.read_text())["tiers"]["smoke"][0]
            (root / first / "prompt_instruction.txt").write_text("CHANGED", encoding="utf8")
            out = base / "public_generator"
            with self.assertRaisesRegex(stager.StagingError, "hash mismatch"):
                stager.stage(root, suite, "smoke", out)
            self.assertFalse(out.exists())

    def test_bad_suite_and_symlink_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "dataset"
            root.mkdir()
            suite = self.prepare(root)
            manifest = json.loads(suite.read_text())
            manifest["dataset_revision"] = "unversioned-main"
            suite.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(stager.StagingError, "pinned"):
                stager.stage(root, suite, "smoke", base / "out")
            suite.write_text(json.dumps(selector.select(root, "a" * 40)))
            task = json.loads(suite.read_text())["tiers"]["smoke"][0]
            source = root / task / "prompt_description.txt"
            source.unlink()
            source.symlink_to(base / "outside")
            with self.assertRaisesRegex(stager.StagingError, "Unsafe"):
                stager.stage(root, suite, "smoke", base / "out")
            self.assertFalse((base / "out").exists())

    def test_no_reference_file_read_is_required_for_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "dataset"
            root.mkdir()
            suite = self.prepare(root)
            task = json.loads(suite.read_text())["tiers"]["smoke"][0]
            # An unreadable or missing hidden reference in scoring workspace
            # cannot affect prompt-only staging; we never consult it.
            (root / task / f"{task}.py").unlink()
            report = stager.stage(root, suite, "smoke", base / "out")
            self.assertEqual(report["task_count"], 6)


if __name__ == "__main__":
    unittest.main()
