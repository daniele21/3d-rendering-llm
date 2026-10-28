"""Fast benchmark-data boundary tests; no Hugging Face download or Blender needed."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "benchmarks/catalog/select_suites.py"
spec = importlib.util.spec_from_file_location("select_suites", MODULE)
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)
REVISION = "a" * 40


def fixture(root: Path, count: int = 30):
    for i in range(count):
        name = f"Example{i:02d}_seed0"
        folder = root / name
        folder.mkdir()
        (folder / "prompt_description.txt").write_text(f"Object {i} with legs", encoding="utf-8")
        (folder / "prompt_instruction.txt").write_text(f"Construct {i}", encoding="utf-8")
        (folder / f"{name}.py").write_text("SECRET_REFERENCE_FACTORY = True", encoding="utf-8")


class BenchmarkCatalogTests(unittest.TestCase):
    def test_deterministic_leak_safe_and_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            a = catalog.select(root, REVISION)
            b = catalog.select(root, REVISION)
            self.assertEqual(a, b)
            self.assertEqual((len(a["tiers"]["smoke"]), len(a["tiers"]["core"]), len(a["tiers"]["full"])), (6, 24, 30))
            self.assertTrue(set(a["tiers"]["smoke"]) <= set(a["tiers"]["core"]))
            self.assertNotIn("SECRET_REFERENCE_FACTORY", json.dumps(a))
            self.assertNotIn(".py", json.dumps(a))
            self.assertIn("provisional", a["selection"])

    def test_bad_revision_or_too_few_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, 8)
            with self.assertRaisesRegex(catalog.CatalogError, "40-hex"):
                catalog.select(root, "main")
            with self.assertRaisesRegex(catalog.CatalogError, "24"):
                catalog.select(root, REVISION)

    def test_unknown_curated_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            base = catalog.select(root, REVISION)
            smoke = base["tiers"]["smoke"]
            core = list(base["tiers"]["core"])
            core[0] = "Unknown_seed0"
            with self.assertRaises(catalog.CatalogError):
                catalog.select(root, REVISION, {"smoke": smoke, "core": core})

    def test_missing_reference_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            (root / "Example00_seed0" / "Example00_seed0.py").unlink()
            with self.assertRaises(catalog.CatalogError):
                catalog.discover(root)
            (root / "Example00_seed0" / "Example00_seed0.py").symlink_to(Path(tmp) / "outside.py")
            with self.assertRaises(catalog.CatalogError):
                catalog.discover(root)


if __name__ == "__main__":
    unittest.main()
